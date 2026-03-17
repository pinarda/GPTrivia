import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import PushSubscription


class NotificationSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(self.user)

    @patch("GPTrivia.views.webpush")
    def test_save_subscription_creates_subscription_for_authenticated_user(self, mock_webpush):
        response = self.client.post(
            reverse("save_subscription"),
            data=json.dumps(
                {
                    "endpoint": "https://example.com/push/123",
                    "keys": {
                        "p256dh": "test-p256dh",
                        "auth": "test-auth",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "test_notification_sent": True},
        )

        subscription = PushSubscription.objects.get(endpoint="https://example.com/push/123")
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.p256dh, "test-p256dh")
        self.assertEqual(subscription.auth, "test-auth")
        mock_webpush.assert_called_once()

    def test_delete_subscription_removes_matching_endpoint(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://example.com/push/123",
            p256dh="test-p256dh",
            auth="test-auth",
        )

        response = self.client.delete(
            reverse("save_subscription"),
            data=json.dumps({"endpoint": "https://example.com/push/123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "deleted": True})
        self.assertFalse(PushSubscription.objects.filter(endpoint="https://example.com/push/123").exists())
