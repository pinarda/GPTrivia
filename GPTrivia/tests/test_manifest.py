from django.test import TestCase
from django.urls import reverse


class WebAppManifestTests(TestCase):
    def test_desktop_manifest_starts_at_home(self):
        response = self.client.get(
            reverse('web_app_manifest'),
            HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        self.assertEqual(response.json()['start_url'], reverse('home'))

    def test_mobile_manifest_starts_at_answer_sheet(self):
        response = self.client.get(
            reverse('web_app_manifest'),
            HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['start_url'], reverse('answer_sheet'))
