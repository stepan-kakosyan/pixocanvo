from django.test import SimpleTestCase
from django.urls import reverse


class PublicPagesSmokeTests(SimpleTestCase):
    def test_privacy_page_returns_ok(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pixelwar/privacy.html")
