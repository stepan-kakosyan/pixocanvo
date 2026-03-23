from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic import TemplateView

from pixelwar.sitemaps import sitemaps

handler404 = "pixelwar.views.custom_404"
handler500 = "pixelwar.views.custom_500"

urlpatterns = [
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
        name="robots",
    ),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("auth/", include("users.urls")),
    path(
        "notifications/",
        include(("Notifications.urls", "notifications"), namespace="notifications"),
    ),
    path("", include("pixelwar.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG and not getattr(settings, "USE_S3", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
