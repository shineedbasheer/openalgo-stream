"""
config.py
---------
Centralised configuration for the Order Tracker service.
All values can be overridden via environment variables so that the
same image/code runs in dev, staging, and production without changes.

IMPORTANT — lazy loading
~~~~~~~~~~~~~~~~~~~~~~~~
Config values are read via @property so that os.environ is sampled at
the moment each value is first accessed, NOT at import time.
This is critical because Flask/dotenv loads the .env file AFTER Python
has already imported all modules.  A class-level assignment like:
    POLL_INTERVAL_SECONDS = float(os.getenv(...))
would run before .env is loaded and always return the default.
"""

import os


def _env(key: str, default: str = "") -> str:
    """Read env var and strip surrounding quotes/whitespace (handles .env quirks)."""
    val = os.getenv(key, default)
    return val.strip().strip("'\"")


class Config:

    # ------------------------------------------------------------------ #
    # OpenAlgo API
    # ------------------------------------------------------------------ #

    @property
    def OPENALGO_BASE_URL(self) -> str:
        return _env("OPENALGO_BASE_URL", "http://127.0.0.1:5000")

    @property
    def OPENALGO_API_KEY(self) -> str:
        return _env("OPENALGO_API_KEY", "")

    @property
    def ORDERBOOK_URL(self) -> str:
        return f"{self.OPENALGO_BASE_URL}/api/v1/orderbook"

    @property
    def HTTP_TIMEOUT(self) -> int:
        return int(_env("HTTP_TIMEOUT", "10"))

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #

    @property
    def POLL_INTERVAL_SECONDS(self) -> float:
        return float(_env("POLL_INTERVAL_SECONDS", "2"))

    # ------------------------------------------------------------------ #
    # Kafka
    # ------------------------------------------------------------------ #

    @property
    def KAFKA_BOOTSTRAP_SERVERS(self) -> str:
        return _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    @property
    def KAFKA_TOPIC(self) -> str:
        return _env("KAFKA_ORDER_EVENTS_TOPIC", "from_openalgo_order_events")

    @property
    def KAFKA_COMPRESSION(self) -> str:
        return _env("KAFKA_PRODUCER_COMPRESSION", "snappy")

    @property
    def KAFKA_BATCH_SIZE(self) -> int:
        return int(_env("KAFKA_PRODUCER_BATCH_SIZE", "16384"))

    @property
    def KAFKA_LINGER_MS(self) -> int:
        return int(_env("KAFKA_PRODUCER_LINGER_MS", "10"))

    @property
    def KAFKA_ACKS(self) -> str:
        return _env("KAFKA_PRODUCER_ACKS", "all")

    @property
    def KAFKA_RETRIES(self) -> int:
        return int(_env("KAFKA_PRODUCER_RETRIES", "3"))

    @property
    def KAFKA_REQUEST_TIMEOUT_MS(self) -> int:
        return int(_env("KAFKA_PRODUCER_REQUEST_TIMEOUT_MS", "30000"))

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #

    @property
    def LOG_LEVEL(self) -> str:
        return _env("LOG_LEVEL", "INFO")


# Singleton instance — import this everywhere.
# Because all values are @property, they are read from os.environ
# at access time, not at import time.
config = Config()
