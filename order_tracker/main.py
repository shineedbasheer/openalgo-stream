"""
main.py
-------
Entry point for the Order Tracker service.

Run:
    python -m order_tracker.main
    # or
    python order_tracker/main.py

The process runs until SIGINT (Ctrl-C) or SIGTERM is received, then
performs a clean shutdown: flushes the Kafka producer and exits with
code 0.
"""

from __future__ import annotations

import logging
import signal
import sys
import time

from order_tracker.config import config
from order_tracker.kafka_publisher import KafkaPublisher
from order_tracker.order_tracker import OrderTracker
from order_tracker.orderbook_client import OrderbookClient


# ------------------------------------------------------------------ #
# Logging setup
# ------------------------------------------------------------------ #

def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# ------------------------------------------------------------------ #
# Bootstrap
# ------------------------------------------------------------------ #

def _validate_config() -> None:
    """Fail fast with a clear error if critical config is missing."""
    if not config.OPENALGO_API_KEY:
        sys.exit(
            "[FATAL] OPENALGO_API_KEY is not set. "
            "Export it as an environment variable or add it to your .env file."
        )
    if not config.KAFKA_BOOTSTRAP_SERVERS:
        sys.exit(
            "[FATAL] KAFKA_BOOTSTRAP_SERVERS is not set."
        )


def _build_components() -> OrderTracker:
    """Wire up all components and return a ready-to-start OrderTracker."""
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


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("OpenAlgo Order Tracker starting up")
    logger.info("  OpenAlgo URL  : %s", config.OPENALGO_BASE_URL)
    logger.info("  Kafka brokers : %s", config.KAFKA_BOOTSTRAP_SERVERS)
    logger.info("  Kafka topic   : %s", config.KAFKA_TOPIC)
    logger.info("  Poll interval : %.1fs", config.POLL_INTERVAL_SECONDS)
    logger.info("=" * 60)

    _validate_config()
    tracker = _build_components()

    # ---- Graceful shutdown on SIGINT / SIGTERM ----------------------
    def _handle_signal(signum, frame):  # noqa: ARG001
        logger.info("Signal %s received — initiating graceful shutdown...", signum)
        tracker.stop(timeout=15.0)
        logger.info("Order Tracker stopped. Bye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ---- Start ------------------------------------------------------
    tracker.start()
    logger.info("Order Tracker is running. Press Ctrl-C to stop.")

    # Keep the main thread alive so daemon thread keeps running
    try:
        while True:
            time.sleep(5)
            logger.debug(
                "Heartbeat — tracked=%d pending=%d",
                tracker.total_count,
                tracker.pending_count,
            )
    except KeyboardInterrupt:
        # Fallback in case signal handler isn't called (e.g. Windows)
        logger.info("KeyboardInterrupt — shutting down...")
        tracker.stop(timeout=15.0)
        logger.info("Order Tracker stopped. Bye.")


if __name__ == "__main__":
    main()
