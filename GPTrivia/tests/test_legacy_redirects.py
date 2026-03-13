from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LegacyPageRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="test-pass")
        self.client.force_login(self.user)

    def test_legacy_scoresheet_redirects_to_scoresheet_new(self):
        response = self.client.get(reverse("scoresheet"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scoresheet_new"))

    def test_legacy_analysis_redirects_to_current_analysis(self):
        response = self.client.get(reverse("player_analysis_legacy"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("player_analysis"))
