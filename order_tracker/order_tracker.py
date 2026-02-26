"""
order_tracker.py
----------------
Core engine of the service.

Responsibilities
~~~~~~~~~~~~~~~~
1. Maintain executionTracker: Dict[str, OrderWrapper]
2. On each poll tick:
   a. Fetch orders from OrderbookClient.
   b. Apply Case-A / Case-B diff logic to update executionTracker.
   c. Publish all unsent (send_flag=False) wrappers via KafkaPublisher.
   d. Mark successfully published wrappers as sent (send_flag=True).
3. Run the poll loop in a background thread; expose start() / stop().

Thread-safety
~~~~~~~~~~~~~
executionTracker is mutated only inside _process_orders(), which is called
exclusively from the single polling thread.  KafkaPublisher is itself
thread-safe (has its own lock on producer creation).  If you ever call
process_orders() from multiple threads, wrap the entire method body with
self._tracker_lock.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List

from order_tracker.kafka_publisher import KafkaPublisher, KafkaPublisherConnectionError
from order_tracker.order_wrapper import OrderWrapper
from order_tracker.orderbook_client import (
    OrderbookClient,
    OrderbookClientError,
    OrderbookConnectionError,
    OrderbookTimeoutError,
)

logger = logging.getLogger(__name__)


class OrderTracker:
    """
    Stateful engine that polls OpenAlgo and publishes state changes to Kafka.

    Parameters
    ----------
    orderbook_client  : Configured OrderbookClient instance.
    kafka_publisher   : Configured KafkaPublisher instance.
    api_key           : OpenAlgo API key — embedded in every Kafka payload.
    poll_interval     : Seconds between orderbook polls (default 2).
    """

    def __init__(
        self,
        orderbook_client: OrderbookClient,
        kafka_publisher: KafkaPublisher,
        api_key: str,
        poll_interval: float = 2.0,
    ) -> None:
        self._client = orderbook_client
        self._publisher = kafka_publisher
        self._api_key = api_key
        self._poll_interval = poll_interval

        # Primary state — keyed by executionId (= orderid)
        self._execution_tracker: Dict[str, OrderWrapper] = {}

        # Protects _execution_tracker from concurrent reads during shutdown
        self._tracker_lock = threading.Lock()

        # Background polling thread control
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        logger.info(
            "OrderTracker initialised. poll_interval=%.1fs", self._poll_interval
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the background polling thread. Idempotent."""
        if self._thread and self._thread.is_alive():
            logger.warning("OrderTracker is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="OrderTrackerPollLoop",
            daemon=True,       # exits automatically when main thread dies
        )
        self._thread.start()
        logger.info("OrderTracker polling started.")

    def stop(self, timeout: float = 10.0) -> None:
        """
        Signal the poll loop to exit and wait for the thread to finish.
        Flushes the Kafka producer before returning.
        """
        logger.info("OrderTracker stopping...")
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    "OrderTracker thread did not exit within %.1fs.", timeout
                )

        self._publisher.flush()
        self._publisher.close()
        logger.info("OrderTracker stopped.")

    # ------------------------------------------------------------------ #
    # Poll loop
    # ------------------------------------------------------------------ #

    def _poll_loop(self) -> None:
        """
        Runs in the background thread.
        Fetches orders, applies diff logic, publishes to Kafka, sleeps.
        """
        logger.info("Poll loop started.")

        # Wait for Flask to finish binding before the first poll.
        # OrderTracker starts inside setup_environment() while Flask is still
        # initialising — without this delay the first 1-2 ticks hit a
        # "connection refused" / timeout since port 5000 isn't open yet.
        STARTUP_DELAY = 5.0   # seconds — enough for Flask + all blueprints to load
        logger.info("Waiting %.0fs for Flask to finish startup...", STARTUP_DELAY)
        if self._stop_event.wait(timeout=STARTUP_DELAY):
            logger.info("Stop requested during startup delay — exiting.")
            return

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                # Catch-all so a single bad tick never kills the thread
                logger.error("Unexpected error in poll tick: %s", exc, exc_info=True)

            # Use wait() so stop() can interrupt the sleep immediately
            self._stop_event.wait(timeout=self._poll_interval)

        logger.info("Poll loop exited.")

    def _tick(self) -> None:
        """Single poll-process-publish cycle."""
        orders = self._fetch_orders_safe()
        if orders is None:
            return  # Fetch failed; error already logged; try again next tick

        self._process_orders(orders)
        self._publish_pending()

    # ------------------------------------------------------------------ #
    # Step 1 — Fetch
    # ------------------------------------------------------------------ #

    def _fetch_orders_safe(self) -> List[dict] | None:
        """
        Wrap the HTTP fetch in error handling.
        Returns the list of orders, or None on failure.
        """
        try:
            return self._client.fetch_orders()

        except OrderbookConnectionError as exc:
            logger.warning("Cannot reach OpenAlgo (will retry): %s", exc)

        except OrderbookTimeoutError as exc:
            logger.warning("Orderbook request timed out (will retry): %s", exc)

        except OrderbookClientError as exc:
            logger.error("Orderbook client error: %s", exc)

        return None

    # ------------------------------------------------------------------ #
    # Step 2 — Diff logic (Case A / Case B)
    # ------------------------------------------------------------------ #

    def _process_orders(self, orders: List[dict]) -> None:
        """
        Apply the execution tracker diff logic for every order in the list.

        Case A — executionId NOT in tracker  → insert new OrderWrapper (send_flag=False)
        Case B — executionId EXISTS           → compare status + quantity
                   changed  → overwrite order, reset send_flag=False
                   unchanged → do nothing (idempotent)
        """
        with self._tracker_lock:
            for raw_order in orders:
                execution_id = str(raw_order.get("orderid", "")).strip()

                if not execution_id:
                    logger.warning(
                        "Order with missing/empty orderid skipped: %s", raw_order
                    )
                    continue

                if execution_id not in self._execution_tracker:
                    # ---- Case A: brand new order ----------------------
                    wrapper = OrderWrapper(order=raw_order, send_flag=False)
                    self._execution_tracker[execution_id] = wrapper
                    logger.info(
                        "Case A — New order tracked. executionId=%s status=%s qty=%d",
                        execution_id,
                        wrapper.status,
                        wrapper.quantity,
                    )

                else:
                    # ---- Case B: order already known ------------------
                    wrapper = self._execution_tracker[execution_id]

                    status_changed = wrapper.has_status_changed(raw_order)
                    qty_changed = wrapper.has_quantity_changed(raw_order)

                    if status_changed or qty_changed:
                        old_status = wrapper.status
                        old_qty = wrapper.quantity
                        wrapper.update_order(raw_order)   # resets send_flag=False
                        logger.info(
                            "Case B — Order changed. executionId=%s "
                            "status: %s→%s qty: %d→%d",
                            execution_id,
                            old_status,
                            wrapper.status,
                            old_qty,
                            wrapper.quantity,
                        )
                    else:
                        logger.debug(
                            "Case B — No change. executionId=%s status=%s",
                            execution_id,
                            wrapper.status,
                        )

    # ------------------------------------------------------------------ #
    # Step 3 — Publish pending wrappers
    # ------------------------------------------------------------------ #

    def _publish_pending(self) -> None:
        """
        Iterate executionTracker and publish every wrapper where
        send_flag == False.  Marks as sent only on successful delivery.
        """
        with self._tracker_lock:
            pending = [
                w for w in self._execution_tracker.values() if not w.send_flag
            ]

        if not pending:
            logger.debug("No pending wrappers to publish.")
            return

        logger.debug("Publishing %d pending wrapper(s).", len(pending))

        for wrapper in pending:
            payload = wrapper.to_kafka_payload(api_key=self._api_key)
            try:
                success = self._publisher.publish(
                    payload=payload,
                    key=wrapper.execution_id,
                )
                if success:
                    wrapper.mark_sent()
                    logger.info(
                        "Published order event. executionId=%s status=%s "
                        "filledQty=%s placedQty=%s",
                        wrapper.execution_id,
                        wrapper.status,
                        payload["filledQty"],
                        payload["placedQty"],
                    )
                else:
                    # publish() returned False — transient failure, will retry
                    logger.warning(
                        "Kafka publish returned False for executionId=%s. "
                        "Will retry next tick.",
                        wrapper.execution_id,
                    )

            except KafkaPublisherConnectionError as exc:
                # Producer itself is broken; log and bail out of this tick
                logger.error(
                    "Kafka connection error — aborting publish cycle: %s", exc
                )
                break

            except Exception as exc:
                logger.error(
                    "Unexpected error publishing executionId=%s: %s",
                    wrapper.execution_id,
                    exc,
                    exc_info=True,
                )

    # ------------------------------------------------------------------ #
    # Introspection (useful for testing / health checks)
    # ------------------------------------------------------------------ #

    @property
    def tracker_snapshot(self) -> Dict[str, OrderWrapper]:
        """Return a shallow copy of the current execution tracker."""
        with self._tracker_lock:
            return dict(self._execution_tracker)

    @property
    def pending_count(self) -> int:
        """Number of wrappers waiting to be published."""
        with self._tracker_lock:
            return sum(1 for w in self._execution_tracker.values() if not w.send_flag)

    @property
    def total_count(self) -> int:
        """Total number of orders currently tracked."""
        with self._tracker_lock:
            return len(self._execution_tracker)
