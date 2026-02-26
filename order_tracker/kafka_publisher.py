"""
kafka_publisher.py
------------------
Thin, thread-safe wrapper around a kafka-python KafkaProducer.

Responsibilities
~~~~~~~~~~~~~~~~
* Own the KafkaProducer lifecycle (create, publish, close).
* Serialise payloads to UTF-8 JSON bytes.
* Expose a simple publish(payload: dict) → bool interface so the rest
  of the application never touches kafka-python directly.
* Provide lazy initialisation — the producer is only created on first use,
  so import-time Kafka connectivity is never required.
* Raise typed exceptions so callers can react appropriately.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Custom exceptions
# ------------------------------------------------------------------ #

class KafkaPublisherError(Exception):
    """Base exception for publisher failures."""


class KafkaPublisherConnectionError(KafkaPublisherError):
    """Raised when the producer cannot connect to the Kafka cluster."""


class KafkaPublisherSendError(KafkaPublisherError):
    """Raised when a message cannot be delivered after retries."""


# ------------------------------------------------------------------ #
# Publisher
# ------------------------------------------------------------------ #

class KafkaPublisher:
    """
    Thread-safe Kafka producer wrapper.

    Parameters
    ----------
    bootstrap_servers : Comma-separated broker list, e.g. 'localhost:9092'.
    topic             : Target Kafka topic name.
    compression_type  : 'snappy' | 'gzip' | 'lz4' | 'zstd' | None.
    batch_size        : Producer batch size in bytes.
    linger_ms         : Producer linger time in milliseconds.
    acks              : '0' | '1' | 'all'.
    retries           : Number of automatic retries on transient failures.
    request_timeout_ms: Per-request timeout in milliseconds.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        compression_type: str = "snappy",
        batch_size: int = 16384,
        linger_ms: int = 10,
        acks: str = "all",
        retries: int = 3,
        request_timeout_ms: int = 30000,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._compression_type = compression_type or None  # '' → None
        self._batch_size = batch_size
        self._linger_ms = linger_ms
        self._acks = acks
        self._retries = retries
        self._request_timeout_ms = request_timeout_ms

        # Producer is created lazily on first publish()
        self._producer = None
        self._lock = threading.Lock()

        logger.info(
            "KafkaPublisher configured. brokers=%s topic=%s",
            self._bootstrap_servers,
            self._topic,
        )

    # ------------------------------------------------------------------ #
    # Lazy producer initialisation
    # ------------------------------------------------------------------ #

    def _get_producer(self):
        """
        Return the shared KafkaProducer, creating it on first call.
        Protected by a lock so concurrent threads don't race on creation.
        """
        if self._producer is not None:
            return self._producer

        with self._lock:
            # Double-checked locking pattern
            if self._producer is not None:
                return self._producer

            try:
                from kafka import KafkaProducer  # lazy import
                from kafka.errors import KafkaError

                producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    compression_type=self._compression_type,
                    batch_size=self._batch_size,
                    linger_ms=self._linger_ms,
                    acks=self._acks,
                    retries=self._retries,
                    request_timeout_ms=self._request_timeout_ms,
                    # Note: enable_idempotence is NOT supported in kafka-python 2.0.2
                    # Idempotency is handled at application level via send_flag
                )
                self._producer = producer
                logger.info(
                    "KafkaProducer connected to %s", self._bootstrap_servers
                )
                return self._producer

            except ImportError as exc:
                raise KafkaPublisherError(
                    "kafka-python is not installed. "
                    "Run: pip install kafka-python==2.0.2"
                ) from exc

            except Exception as exc:
                raise KafkaPublisherConnectionError(
                    f"Failed to create KafkaProducer: {exc}"
                ) from exc

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def publish(self, payload: Dict[str, Any], key: str | None = None) -> bool:
        """
        Publish a single dict payload to the configured Kafka topic.

        Parameters
        ----------
        payload : Message body — will be JSON-serialised.
        key     : Optional Kafka message key (used for partition routing).
                  Defaults to payload['executionId'] if present.

        Returns
        -------
        bool
            True on successful delivery, False on failure (caller decides
            whether to retry or skip).
        """
        if key is None:
            key = payload.get("executionId")

        try:
            producer = self._get_producer()

            # send() is non-blocking; .get() waits for broker ack
            future = producer.send(self._topic, value=payload, key=key)
            record_metadata = future.get(timeout=self._request_timeout_ms / 1000)

            logger.info(
                "Published to Kafka. topic=%s partition=%d offset=%d key=%s status=%s",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
                key,
                payload.get("status"),
            )
            return True

        except KafkaPublisherConnectionError:
            # Re-raise so caller knows the producer itself is broken
            raise

        except Exception as exc:
            # Covers KafkaTimeoutError, NotLeaderForPartitionError, etc.
            logger.error(
                "Failed to publish to Kafka. topic=%s key=%s error=%s",
                self._topic,
                key,
                exc,
                exc_info=True,
            )
            return False

    def flush(self, timeout: float = 10.0) -> None:
        """
        Block until all buffered messages are delivered or timeout expires.
        Safe to call even if the producer was never initialised.
        """
        if self._producer:
            self._producer.flush(timeout=timeout)
            logger.debug("KafkaProducer flushed.")

    def close(self) -> None:
        """Flush pending messages and release producer resources."""
        if self._producer:
            try:
                self._producer.flush(timeout=10)
                self._producer.close(timeout=10)
                logger.info("KafkaProducer closed cleanly.")
            except Exception as exc:
                logger.warning("Error closing KafkaProducer: %s", exc)
            finally:
                self._producer = None
