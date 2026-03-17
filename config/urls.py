from django.conf import settings
from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("auth/", include("users.urls")),
    path("", include("pixelwar.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
