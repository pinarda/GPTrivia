import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
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


class ScheduledNotificationTests(TestCase):
    @patch("GPTrivia.management.commands.send_trivia_push.send_push_to_all")
    @patch("GPTrivia.management.commands.send_trivia_push.async_to_sync")
    def test_send_trivia_push_counts_only_unused_round_creators(self, mock_async_to_sync, mock_send_push):
        mock_async_to_sync.return_value = lambda: [
            {"creator": "Alex", "is_new": True},
            {"creator": "Megan", "is_new": True},
            {"creator": "Jenny", "is_new": False},
            {"creator": "Chris", "is_new": False},
        ]

        call_command("send_trivia_push")

        mock_send_push.assert_called_once_with(
            "Trivia at 7:30pm PST!",
            "We have rounds from 2 different creators (Alex, Megan).",
        )
