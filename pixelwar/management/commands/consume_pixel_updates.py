import json
import time
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import NotSupportedError
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from pixelwar.models import ChatMessage, Community, Pixel


class Command(BaseCommand):
    help = "Consume Kafka pixel updates, bulk-upsert to DB, and broadcast via websocket"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--flush-interval", type=float, default=1.0)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        flush_interval = options["flush_interval"]
        pixel_topic = settings.KAFKA_PIXEL_TOPIC
        chat_topic = settings.KAFKA_CHAT_TOPIC

        consumer = self._create_consumer([pixel_topic, chat_topic])

        self.stdout.write(
            self.style.SUCCESS(
                f"Consuming topics: '{pixel_topic}', '{chat_topic}'..."
            )
        )

        pixel_buffer: list[dict[str, Any]] = []
        chat_buffer: list[dict[str, Any]] = []
        last_flush = time.monotonic()

        while True:
            polled = consumer.poll(timeout_ms=200, max_records=batch_size)
            for records in polled.values():
                for record in records:
                    payload = record.value
                    topic = record.topic
                    if topic == pixel_topic and self._valid_pixel(payload):
                        pixel_buffer.append(payload)
                    elif topic == chat_topic and self._valid_chat(payload):
                        chat_buffer.append(payload)

            now = time.monotonic()
            should_flush = (
                len(pixel_buffer) >= batch_size
                or len(chat_buffer) >= batch_size
                or (
                    (pixel_buffer or chat_buffer)
                    and now - last_flush >= flush_interval
                )
            )
            if should_flush:
                if pixel_buffer:
                    self._flush_pixels(pixel_buffer)
                    pixel_buffer = []
                if chat_buffer:
                    self._flush_chat(chat_buffer)
                    chat_buffer = []
                last_flush = now

    def _create_consumer(self, topics: list[str]) -> KafkaConsumer:
        retry_backoff = float(
            getattr(settings, "KAFKA_CONSUMER_CONNECT_RETRY_BACKOFF", 2.0)
        )

        while True:
            try:
                return KafkaConsumer(
                    *topics,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    auto_offset_reset=settings.KAFKA_CONSUMER_AUTO_OFFSET_RESET,
                    enable_auto_commit=True,
                    group_id=settings.KAFKA_CONSUMER_GROUP_ID,
                    value_deserializer=lambda value: json.loads(
                        value.decode("utf-8")
                    ),
                )
            except NoBrokersAvailable:
                self.stdout.write(
                    self.style.WARNING(
                        "Kafka not ready for consumer yet, retrying..."
                    )
                )
                time.sleep(retry_backoff)

    def _valid_pixel(self, payload: dict[str, Any]) -> bool:
        return (
            isinstance(payload.get("community_slug"), str)
            and payload.get("community_slug") != ""
            and isinstance(payload.get("x"), int)
            and isinstance(payload.get("y"), int)
            and isinstance(payload.get("color"), str)
        )

    def _valid_chat(self, payload: dict[str, Any]) -> bool:
        return (
            isinstance(payload.get("community_slug"), str)
            and payload.get("community_slug") != ""
            and isinstance(payload.get("user_id"), int)
            and isinstance(payload.get("username"), str)
            and isinstance(payload.get("message"), str)
        )

    def _flush_pixels(self, payloads: list[dict[str, Any]]) -> None:
        latest_by_coord: dict[tuple[str, int, int], dict[str, Any]] = {}
        for payload in payloads:
            key = (payload["community_slug"], payload["x"], payload["y"])
            latest_by_coord[key] = payload

        community_slugs = {point[0] for point in latest_by_coord.keys()}
        communities = {
            item.slug: item
            for item in Community.objects.filter(slug__in=community_slugs)
        }

        rows = []
        for point, data in latest_by_coord.items():
            community = communities.get(point[0])
            if community is None:
                continue
            rows.append(
                Pixel(
                    community=community,
                    x=point[1],
                    y=point[2],
                    color=data["color"],
                )
            )

        if rows:
            with transaction.atomic():
                try:
                    Pixel.objects.bulk_create(
                        rows,
                        update_conflicts=True,
                        update_fields=["color", "updated_at"],
                        unique_fields=["community", "x", "y"],
                    )

                except (TypeError, NotSupportedError):
                    for row in rows:
                        Pixel.objects.update_or_create(
                            community=row.community,
                            x=row.x,
                            y=row.y,
                            defaults={"color": row.color},
                        )

        channel_layer = get_channel_layer()
        for point, data in latest_by_coord.items():
            community_slug = point[0]
            if community_slug not in communities:
                continue
            message = {
                "x": point[1],
                "y": point[2],
                "color": data["color"],
                "user_key": data.get("user_key", ""),
            }
            async_to_sync(channel_layer.group_send)(
                f"pixel_updates_{community_slug}",
                {
                    "type": "pixel_update",
                    "payload": message,
                },
            )

    def _flush_chat(self, payloads: list[dict[str, Any]]) -> None:
        user_ids = {payload["user_id"] for payload in payloads}
        community_slugs = {payload["community_slug"] for payload in payloads}
        communities = {
            item.slug: item
            for item in Community.objects.filter(slug__in=community_slugs)
        }
        existing_users = set(
            User.objects.filter(id__in=user_ids).values_list("id", flat=True)
        )

        rows: list[ChatMessage] = []
        for payload in payloads:
            user_id = payload["user_id"]
            community = communities.get(payload["community_slug"])
            if user_id not in existing_users or community is None:
                continue
            message = str(payload.get("message", "")).strip()
            if not message:
                continue
            rows.append(
                ChatMessage(
                    community=community,
                    user_id=user_id,
                    message=message[:500],
                )
            )

        if rows:
            ChatMessage.objects.bulk_create(rows, batch_size=500)

        channel_layer = get_channel_layer()
        for payload in payloads:
            community_slug = payload["community_slug"]
            if payload["user_id"] not in existing_users:
                continue
            if community_slug not in communities:
                continue
            message = {
                "username": payload["username"],
                "avatar_url": payload.get("avatar_url", ""),
                "message": str(payload.get("message", ""))[:500],
                "created_at": payload.get("created_at"),
            }
            async_to_sync(channel_layer.group_send)(
                f"chat_messages_{community_slug}",
                {
                    "type": "chat_message",
                    "payload": message,
                },
            )
