from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("read-all/", views.mark_all_notifications_read, name="mark-all-read"),
    path("open/<int:notification_id>/", views.open_notification, name="open"),
    path("mark/<int:notification_id>/", views.mark_notification_read, name="mark-read"),
]
