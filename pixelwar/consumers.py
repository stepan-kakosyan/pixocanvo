import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import CommunityMembership


async def _is_active_member(user, slug: str) -> bool:
    if slug == "global":
        return True
    if not user or not user.is_authenticated:
        return False
    return await database_sync_to_async(
        CommunityMembership.objects.filter(
            community__slug=slug,
            user=user,
            active=True,
        ).exists
    )()


class PixelStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.community_slug = self.scope["url_route"]["kwargs"].get(
            "community_slug",
            "",
        )
        self.group_name = f"pixel_updates_{self.community_slug}"

        if not await _is_active_member(self.scope.get("user"), self.community_slug):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def pixel_update(self, event: dict) -> None:
        await self.send(text_data=json.dumps(event["payload"]))

    async def pixel_revert(self, event: dict) -> None:
        await self.send(text_data=json.dumps(event["payload"]))


class ChatStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.community_slug = self.scope["url_route"]["kwargs"].get(
            "community_slug",
            "",
        )
        self.group_name = f"chat_messages_{self.community_slug}"

        if not await _is_active_member(self.scope.get("user"), self.community_slug):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def chat_message(self, event: dict) -> None:
        await self.send(text_data=json.dumps(event["payload"]))

    async def chat_revert(self, event: dict) -> None:
        await self.send(text_data=json.dumps(event["payload"]))
