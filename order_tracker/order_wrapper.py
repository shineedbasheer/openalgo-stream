"""
order_wrapper.py
----------------
Wraps a raw order dict from the OpenAlgo orderbook API and tracks
whether the current state has already been published to Kafka.

Design notes
~~~~~~~~~~~~
* Immutable identity  : executionId (= orderid) never changes.
* Mutable state       : order dict and send_flag are updated in-place
                        by OrderTracker under a threading.Lock.
* No external deps    : pure Python dataclass-style class, easy to unit-test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OrderWrapper:
    """
    Wraps a single OpenAlgo order dict with publish-tracking metadata.

    Attributes
    ----------
    order     : The raw order dict returned by the orderbook API.
    send_flag : False  → needs to be published (new or changed).
                True   → already published, nothing to do.
    """

    order: dict
    send_flag: bool = field(default=False)

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #

    @property
    def execution_id(self) -> str:
        """Stable identifier — maps to orderid in OpenAlgo."""
        return str(self.order.get("orderid", ""))

    @property
    def status(self) -> str:
        """Normalised lowercase order_status string."""
        return str(self.order.get("order_status", "")).lower().strip()

    @property
    def quantity(self) -> int:
        """Total placed quantity."""
        try:
            return int(self.order.get("quantity", 0))
        except (TypeError, ValueError):
            return 0

    @property
    def filled_quantity(self) -> int:
        """
        Filled quantity.

        OpenAlgo does not currently expose a dedicated filled_qty field for
        most brokers (partial fills remain in 'open' status with quantity
        fields reflecting what is still pending).  We apply the rule:
            * status == 'complete'  → filledQty = quantity
            * otherwise             → filledQty = 0

        If the API ever starts returning explicit filled_qty / filledqty
        fields, they are preferred automatically.
        """
        # Prefer explicit field if the broker returns it
        for key in ("filled_quantity", "filledqty", "filled_qty", "tradedqty"):
            val = self.order.get(key)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass

        # Fall back to derived rule
        return self.quantity if self.status == "complete" else 0

    @property
    def price(self) -> float:
        """Order price (limit price or average fill price)."""
        try:
            return float(self.order.get("price", 0.0))
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------ #
    # Change-detection helpers (called by OrderTracker)
    # ------------------------------------------------------------------ #

    def has_status_changed(self, incoming_order: dict) -> bool:
        """
        Return True if the order_status in *incoming_order* differs
        from what is currently stored.
        """
        new_status = str(incoming_order.get("order_status", "")).lower().strip()
        changed = new_status != self.status
        if changed:
            logger.debug(
                "Status change detected for executionId=%s: %s → %s",
                self.execution_id,
                self.status,
                new_status,
            )
        return changed

    def has_quantity_changed(self, incoming_order: dict) -> bool:
        """
        Return True if the quantity field in *incoming_order* differs.
        Useful for detecting partial-fill progression when a broker
        updates the remaining quantity on an open order.
        """
        try:
            new_qty = int(incoming_order.get("quantity", 0))
        except (TypeError, ValueError):
            new_qty = 0

        changed = new_qty != self.quantity
        if changed:
            logger.debug(
                "Quantity change detected for executionId=%s: %d → %d",
                self.execution_id,
                self.quantity,
                new_qty,
            )
        return changed

    # ------------------------------------------------------------------ #
    # State mutation
    # ------------------------------------------------------------------ #

    def update_order(self, incoming_order: dict) -> None:
        """Overwrite stored order dict and reset send_flag to False."""
        self.order = incoming_order
        self.send_flag = False
        logger.debug(
            "OrderWrapper updated for executionId=%s, send_flag reset to False.",
            self.execution_id,
        )

    def mark_sent(self) -> None:
        """Called after a successful Kafka publish. Prevents re-publishing."""
        self.send_flag = True
        logger.debug(
            "executionId=%s marked as sent (send_flag=True).", self.execution_id
        )

    # ------------------------------------------------------------------ #
    # Kafka payload builder
    # ------------------------------------------------------------------ #

    def to_kafka_payload(self, api_key: str) -> dict:
        """
        Build the standardised Kafka message payload.

        Schema
        ------
        {
            "executionId" : "<orderid>",
            "apiKey"      : "<apiKey>",
            "filledQty"   : "<filled quantity>",
            "placedQty"   : "<quantity>",
            "filledPrice" : "<price>",
            "status"      : "<order_status>",
            "message"     : "Order status updated"
        }
        """
        return {
            "executionId": self.execution_id,
            "apiKey": api_key,
            "filledQty": str(self.filled_quantity),
            "placedQty": str(self.quantity),
            "filledPrice": str(self.price),
            "status": self.status,
            "message": "Order status updated",
        }

    # ------------------------------------------------------------------ #
    # Dunder helpers
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"OrderWrapper(executionId={self.execution_id!r}, "
            f"status={self.status!r}, "
            f"quantity={self.quantity}, "
            f"send_flag={self.send_flag})"
        )
