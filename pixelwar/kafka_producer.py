import json
import time
from typing import Any

from django.conf import settings
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable


_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is not None:
        return _producer

    attempts = int(getattr(settings, "KAFKA_PRODUCER_CONNECT_ATTEMPTS", 10))
    backoff = float(getattr(settings, "KAFKA_PRODUCER_RETRY_BACKOFF", 1.0))
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            _producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                linger_ms=20,
                acks="all",
                retries=5,
            )
            return _producer
        except NoBrokersAvailable as exc:
            last_error = exc
            time.sleep(backoff)

    if last_error is not None:
        raise last_error

    raise NoBrokersAvailable()


def reset_producer() -> None:
    global _producer
    _producer = None


def enqueue_event(topic: str, payload: dict[str, Any]) -> None:
    producer = get_producer()
    future = producer.send(topic, payload)
    try:
        future.get(timeout=float(getattr(settings, "KAFKA_PRODUCER_SEND_TIMEOUT", 3.0)))
    except KafkaError:
        reset_producer()
        raise


def enqueue_pixel_update(payload: dict[str, Any]) -> None:
    enqueue_event(settings.KAFKA_PIXEL_TOPIC, payload)


def enqueue_chat_message(payload: dict[str, Any]) -> None:
    enqueue_event(settings.KAFKA_CHAT_TOPIC, payload)
