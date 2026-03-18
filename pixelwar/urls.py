from django.urls import path

from . import views

urlpatterns = [
    path("switch-language/", views.switch_language, name="switch-language"),
    path("", views.index, name="index"),
    path("leaders/", views.global_leaders, name="leaders"),
    path("guide/", views.global_guide, name="guide"),
    path("privacy/", views.privacy_policy, name="privacy"),
    path("terms/", views.terms_of_service, name="terms"),
    path("communities/", views.communities_lobby, name="communities"),
    path("communities/create/", views.create_community, name="create-community"),
    path(
        "communities/public/<slug:slug>/request-join/",
        views.request_join_public_community,
        name="request-join-public-community",
    ),
    path("invite/<uuid:token>/", views.invitation_view, name="invitation"),
    path(
        "invite/<uuid:token>/accept/",
        views.invitation_accept,
        name="invitation-accept",
    ),
    path("c/<slug:slug>/", views.community_canvas, name="community-canvas"),
    path(
        "c/<slug:slug>/leaders/",
        views.community_leaders,
        name="community-leaders",
    ),
    path("c/<slug:slug>/details/", views.community_detail, name="community-detail"),
    path(
        "c/<slug:slug>/members/<int:user_id>/remove/",
        views.remove_community_member,
        name="remove-community-member",
    ),
    path(
        "c/<slug:slug>/join-requests/<int:request_id>/approve/",
        views.approve_join_request,
        name="approve-join-request",
    ),
    path(
        "c/<slug:slug>/join-requests/<int:request_id>/decline/",
        views.decline_join_request,
        name="decline-join-request",
    ),
    path("c/<slug:slug>/guide/", views.community_guide, name="community-guide"),
    path("c/<slug:slug>/leave/", views.leave_community, name="leave-community"),
    path("c/<slug:slug>/delete/", views.delete_community, name="delete-community"),
    path("api/pixels/", views.pixel_snapshot, name="pixel_snapshot"),
    path("api/pixels/mine/", views.my_pixels, name="my_pixels"),
    path("api/pixels/update/", views.update_pixel, name="update_pixel"),
    path("api/chat/messages/", views.chat_messages, name="chat_messages"),
    path(
        "api/chat/messages/grouped/",
        views.grouped_chat_messages,
        name="grouped_chat_messages",
    ),
    path("api/chat/send/", views.chat_send, name="chat_send"),
    path(
        "c/<slug:slug>/api/pixels/",
        views.community_pixel_snapshot,
        name="community-pixel-snapshot",
    ),
    path(
        "c/<slug:slug>/api/pixels/mine/",
        views.community_my_pixels,
        name="community-my-pixels",
    ),
    path(
        "c/<slug:slug>/api/pixels/update/",
        views.community_update_pixel,
        name="community-update-pixel",
    ),
    path(
        "c/<slug:slug>/api/chat/messages/",
        views.community_chat_messages,
        name="community-chat-messages",
    ),
    path(
        "c/<slug:slug>/api/chat/send/",
        views.community_chat_send,
        name="community-chat-send",
    ),
]
