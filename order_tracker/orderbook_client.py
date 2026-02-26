"""
orderbook_client.py
-------------------
Thin HTTP client that fetches the live orderbook from the OpenAlgo REST API.

Responsibilities
~~~~~~~~~~~~~~~~
* Build the correct request (POST with apikey in body, per OpenAlgo convention).
* Parse and validate the JSON response envelope.
* Raise typed, descriptive exceptions so the caller (OrderTracker) can
  decide whether to retry or abort.
* Never mutate global state — pure I/O, no side effects.
"""

from __future__ import annotations

import logging
from typing import List

import requests
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout, RequestException

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Custom exceptions — lets callers distinguish failure modes
# ------------------------------------------------------------------ #

class OrderbookClientError(Exception):
    """Base exception for all orderbook client failures."""


class OrderbookConnectionError(OrderbookClientError):
    """Raised when the HTTP connection to OpenAlgo cannot be established."""


class OrderbookTimeoutError(OrderbookClientError):
    """Raised when the HTTP request times out."""


class OrderbookResponseError(OrderbookClientError):
    """Raised when OpenAlgo returns a non-2xx status or malformed JSON."""


# ------------------------------------------------------------------ #
# Client
# ------------------------------------------------------------------ #

class OrderbookClient:
    """
    Fetches orders from GET /api/v1/orderbook.

    Parameters
    ----------
    url        : Full URL of the orderbook endpoint.
    api_key    : OpenAlgo API key sent in the request body.
    timeout    : HTTP read/connect timeout in seconds.
    session    : Optional pre-built requests.Session (useful for testing).
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        timeout: int = 10,
        session: requests.Session | None = None,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._timeout = timeout
        # Reuse a single TCP connection across polls for efficiency
        self._session = session or requests.Session()
        logger.info("OrderbookClient initialised. endpoint=%s", self._url)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_orders(self) -> List[dict]:
        """
        Call the orderbook endpoint and return a list of raw order dicts.

        Returns
        -------
        List[dict]
            Zero or more order dicts exactly as returned by the API.

        Raises
        ------
        OrderbookConnectionError  : Host unreachable / DNS failure.
        OrderbookTimeoutError     : Request took longer than *timeout* seconds.
        OrderbookResponseError    : HTTP error, unexpected JSON shape,
                                    or status != 'success'.
        """
        logger.debug("Fetching orderbook from %s", self._url)

        try:
            # OpenAlgo REST API requires apikey in the POST body (not query param)
            response = self._session.post(
                self._url,
                json={"apikey": self._api_key},
                timeout=self._timeout,
            )
            response.raise_for_status()             # Raises HTTPError on 4xx/5xx

        except ConnectionError as exc:
            raise OrderbookConnectionError(
                f"Cannot reach OpenAlgo at {self._url}: {exc}"
            ) from exc

        except ReadTimeout as exc:
            raise OrderbookTimeoutError(
                f"Orderbook request timed out after {self._timeout}s: {exc}"
            ) from exc

        except HTTPError as exc:
            raise OrderbookResponseError(
                f"HTTP error from orderbook API: {exc}"
            ) from exc

        except RequestException as exc:
            # Catch-all for any other requests library failure
            raise OrderbookClientError(
                f"Unexpected request failure: {exc}"
            ) from exc

        # ---- Parse JSON ------------------------------------------------
        try:
            payload = response.json()
        except ValueError as exc:
            raise OrderbookResponseError(
                f"Orderbook API returned non-JSON body: {response.text[:200]}"
            ) from exc

        # ---- Validate envelope -----------------------------------------
        if payload.get("status") != "success":
            raise OrderbookResponseError(
                f"Orderbook API returned status != 'success': {payload}"
            )

        orders = self._extract_orders(payload)
        logger.debug("Fetched %d order(s) from orderbook.", len(orders))
        return orders

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_orders(payload: dict) -> List[dict]:
        """
        Navigate the response envelope and return the list of orders.

        Expected shape
        --------------
        {
          "status": "success",
          "data": {
            "orders": [ {...}, ... ]
          }
        }

        Falls back gracefully if the structure is slightly different.
        """
        data = payload.get("data", {})

        # Primary path: data.orders
        if isinstance(data, dict):
            orders = data.get("orders")
            if isinstance(orders, list):
                return orders

        # Secondary path: data is itself a list
        if isinstance(data, list):
            return data

        # API returned success but no recognisable orders key — treat as empty
        logger.warning(
            "Orderbook response has unexpected 'data' shape: %s. "
            "Treating as empty orderbook.",
            type(data).__name__,
        )
        return []

    def close(self) -> None:
        """Release the underlying TCP connection pool."""
        self._session.close()
        logger.debug("OrderbookClient HTTP session closed.")
