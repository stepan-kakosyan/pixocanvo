from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Community


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "index",
            "communities",
            "leaders",
            "guide",
            "privacy",
            "terms",
            "contact-us",
        ]

    def location(self, item):
        return reverse(item)


class PublicCommunitySitemap(Sitemap):
    priority = 0.7
    changefreq = "daily"

    def items(self):
        return Community.objects.filter(is_public=True).only("slug", "created_at")

    def lastmod(self, item):
        return item.created_at

    def location(self, item):
        return reverse("community-canvas", kwargs={"slug": item.slug})


sitemaps = {
    "static": StaticViewSitemap,
    "public-communities": PublicCommunitySitemap,
}
