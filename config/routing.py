from django.urls import re_path

from Notifications.consumers import NotificationConsumer
from pixelwar.consumers import ChatStreamConsumer, PixelStreamConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/notifications/$",
        NotificationConsumer.as_asgi(),
    ),
    re_path(
        r"ws/c/(?P<community_slug>[-a-zA-Z0-9_]+)/pixels/$",
        PixelStreamConsumer.as_asgi(),
    ),
    re_path(
        r"ws/c/(?P<community_slug>[-a-zA-Z0-9_]+)/chat/$",
        ChatStreamConsumer.as_asgi(),
    ),
]
