"""
service_manager.py
------------------
Thin integration shim between OpenAlgo (app.py) and the OrderTracker engine.

Follows the EXACT same pattern used by OpenAlgo's own sandbox services:
  - sandbox/execution_thread.py  → start_execution_engine()
  - sandbox/squareoff_thread.py  → start_squareoff_scheduler()

Responsibilities
~~~~~~~~~~~~~~~~
* Provide init_order_tracker(app) — called once from app.py at startup.
* Guard against duplicate starts (thread-safe singleton).
* Read all config from environment via order_tracker.config.
* Register atexit / SIGTERM hooks for clean producer flush on shutdown.
* Expose get_status() for health checks / admin UI.
* Watchdog thread — auto-restarts the tracker if it dies unexpectedly.

What it does NOT do
~~~~~~~~~~~~~~~~~~~
* Does NOT touch Flask request context (order_tracker is I/O only).
* Does NOT import SQLAlchemy models (uses REST API, not DB).
* Does NOT block the main thread (daemon thread).
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Module-level singleton state  (mirrors execution_thread.py pattern)
# ------------------------------------------------------------------ #
_tracker_instance: "OrderTracker | None" = None   # noqa: F821
_instance_lock = threading.Lock()
_is_running = False

# Watchdog thread — monitors the poll loop thread and restarts if dead
_watchdog_thread: threading.Thread | None = None
_watchdog_stop = threading.Event()

# How long the watchdog waits between liveness checks (seconds)
_WATCHDOG_INTERVAL = 10.0

# How many consecutive restarts before watchdog backs off (circuit breaker)
_MAX_RESTARTS = 5
_restart_count = 0
_last_restart_time: float = 0.0


# ------------------------------------------------------------------ #
# Public API — called from app.py
# ------------------------------------------------------------------ #

def init_order_tracker(app=None) -> bool:
    """
    Initialise and start the OrderTracker background service + watchdog.

    Called once from app.py after all databases are initialised.
    Safe to call multiple times — subsequent calls are no-ops.

    Parameters
    ----------
    app : Flask application instance (optional).

    Returns
    -------
    bool  True if started successfully (or already running), False on error.
    """
    global _tracker_instance, _is_running, _watchdog_thread

    # ---- Guard: only start if explicitly enabled --------------------
    # Strip surrounding quotes that dotenv loaders sometimes preserve
    enabled = os.getenv("ORDER_TRACKER_ENABLED", "false").strip().strip("'\"").lower()
    if enabled not in ("true", "1", "yes"):
        logger.debug(
            "OrderTracker disabled (ORDER_TRACKER_ENABLED=%s). Skipping.", enabled
        )
        return False

    with _instance_lock:
        if _is_running and _tracker_instance is not None:
            logger.debug("OrderTracker already running — skipping duplicate init.")
            return True

        try:
            tracker = _build_tracker()
        except Exception as exc:
            logger.error("OrderTracker failed to build: %s", exc, exc_info=True)
            return False

        _tracker_instance = tracker
        _tracker_instance.start()
        _is_running = True

        # ---- Start watchdog -----------------------------------------
        _watchdog_stop.clear()
        _watchdog_thread = threading.Thread(
            target=_watchdog_loop,
            name="OrderTrackerWatchdog",
            daemon=True,
        )
        _watchdog_thread.start()

        # Register clean shutdown hook — mirrors websocket_proxy/app_integration.py
        atexit.register(_shutdown_order_tracker)

        logger.info(
            "OrderTracker started. poll_interval=%.1fs kafka_topic=%s",
            _tracker_instance._poll_interval,
            _tracker_instance._publisher._topic,
        )
        return True


def get_status() -> dict:
    """
    Return a snapshot of the tracker's current state.
    Safe to call from any thread (e.g., a Flask health-check endpoint).
    """
    thread_alive = (
        _tracker_instance is not None
        and _tracker_instance._thread is not None
        and _tracker_instance._thread.is_alive()
    )

    return {
        "running": _is_running and thread_alive,
        "thread_alive": thread_alive,
        "tracked": _tracker_instance.total_count if _tracker_instance else 0,
        "pending": _tracker_instance.pending_count if _tracker_instance else 0,
        "restart_count": _restart_count,
    }


def stop_order_tracker(timeout: float = 10.0) -> None:
    """
    Gracefully stop the watchdog + tracker and flush the Kafka producer.
    Called by the atexit hook and can also be called manually.
    """
    global _tracker_instance, _is_running

    # Stop watchdog first so it doesn't try to restart while we're shutting down
    _watchdog_stop.set()
    if _watchdog_thread and _watchdog_thread.is_alive():
        _watchdog_thread.join(timeout=5.0)

    with _instance_lock:
        if _tracker_instance and _is_running:
            logger.info("Stopping OrderTracker...")
            _tracker_instance.stop(timeout=timeout)
            _is_running = False
            logger.info("OrderTracker stopped.")


# ------------------------------------------------------------------ #
# Watchdog
# ------------------------------------------------------------------ #

def _watchdog_loop() -> None:
    """
    Runs in a daemon thread. Checks every _WATCHDOG_INTERVAL seconds
    whether the OrderTracker poll thread is still alive.

    If it's dead:
      - Rebuilds and restarts the tracker (new thread, fresh state).
      - Applies an exponential back-off circuit breaker after
        _MAX_RESTARTS consecutive failures to avoid hammering a
        permanently broken dependency (e.g. Kafka is down).

    Circuit breaker resets if the tracker stays alive for >60 seconds
    after a restart (counts as a healthy run).
    """
    global _tracker_instance, _restart_count, _last_restart_time

    logger.info("OrderTracker watchdog started. check_interval=%.0fs", _WATCHDOG_INTERVAL)

    while not _watchdog_stop.wait(timeout=_WATCHDOG_INTERVAL):
        with _instance_lock:
            if not _is_running or _tracker_instance is None:
                continue

            thread = _tracker_instance._thread
            if thread is not None and thread.is_alive():
                # Healthy — reset restart counter if we've been stable >60s
                if _restart_count > 0 and (time.time() - _last_restart_time) > 60.0:
                    logger.info(
                        "OrderTracker has been stable for >60s — resetting restart counter."
                    )
                    _restart_count = 0
                continue

            # ---- Thread is dead — attempt restart -------------------
            logger.warning(
                "OrderTracker poll thread is dead! Attempting restart "
                "(restart #%d of %d)...",
                _restart_count + 1,
                _MAX_RESTARTS,
            )

            # Circuit breaker: back off after too many restarts
            if _restart_count >= _MAX_RESTARTS:
                backoff = min(60.0 * _restart_count, 600.0)  # max 10 min
                logger.error(
                    "OrderTracker has been restarted %d times. "
                    "Backing off for %.0fs before next attempt.",
                    _restart_count,
                    backoff,
                )
                # Release lock during sleep so other operations aren't blocked
                _instance_lock.release()
                time.sleep(backoff)
                _instance_lock.acquire()

            # Stop the dead tracker cleanly (flushes Kafka)
            try:
                _tracker_instance.stop(timeout=5.0)
            except Exception as exc:
                logger.warning("Error stopping dead tracker: %s", exc)

            # Rebuild from scratch and restart
            try:
                new_tracker = _build_tracker()
                new_tracker.start()
                _tracker_instance = new_tracker
                _restart_count += 1
                _last_restart_time = time.time()
                logger.info(
                    "OrderTracker restarted successfully (restart #%d).",
                    _restart_count,
                )
            except Exception as exc:
                logger.error(
                    "OrderTracker restart #%d failed: %s",
                    _restart_count + 1,
                    exc,
                    exc_info=True,
                )
                _restart_count += 1
                _last_restart_time = time.time()

    logger.info("OrderTracker watchdog stopped.")


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _build_tracker() -> "OrderTracker":  # noqa: F821
    """
    Wire up OrderbookClient + KafkaPublisher + OrderTracker from config.
    All config values come from environment variables via config.py.
    """
    from order_tracker.config import config
    from order_tracker.kafka_publisher import KafkaPublisher
    from order_tracker.order_tracker import OrderTracker
    from order_tracker.orderbook_client import OrderbookClient

    # ---- Validate critical config -----------------------------------
    if not config.OPENALGO_API_KEY:
        raise ValueError(
            "OPENALGO_API_KEY is not set. "
            "OrderTracker cannot authenticate with the orderbook API."
        )

    if not config.KAFKA_BOOTSTRAP_SERVERS:
        raise ValueError(
            "KAFKA_BOOTSTRAP_SERVERS is not set. "
            "OrderTracker cannot connect to Kafka."
        )

    # ---- Build components -------------------------------------------
    orderbook_client = OrderbookClient(
        url=config.ORDERBOOK_URL,
        api_key=config.OPENALGO_API_KEY,
        timeout=config.HTTP_TIMEOUT,
    )

    kafka_publisher = KafkaPublisher(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        topic=config.KAFKA_TOPIC,
        compression_type=config.KAFKA_COMPRESSION,
        batch_size=config.KAFKA_BATCH_SIZE,
        linger_ms=config.KAFKA_LINGER_MS,
        acks=config.KAFKA_ACKS,
        retries=config.KAFKA_RETRIES,
        request_timeout_ms=config.KAFKA_REQUEST_TIMEOUT_MS,
    )

    tracker = OrderTracker(
        orderbook_client=orderbook_client,
        kafka_publisher=kafka_publisher,
        api_key=config.OPENALGO_API_KEY,
        poll_interval=config.POLL_INTERVAL_SECONDS,
    )

    return tracker


def _shutdown_order_tracker() -> None:
    """atexit hook — ensures Kafka producer is flushed before process exits."""
    stop_order_tracker(timeout=10.0)
