from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia import views
from GPTrivia.models import SubmittedRound


class RoundMakerTests(TestCase):
    @patch("GPTrivia.views.requests.post")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    def test_openai_text_response_uses_http_responses_api_for_legacy_clients(self, post_mock):
        class LegacyClient:
            pass

        post_mock.return_value.json.return_value = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Swoop! Legacy client works.",
                        }
                    ]
                }
            ]
        }

        response = views._create_openai_text_response(
            client=LegacyClient(),
            instructions="Test instructions",
            input_items="Test input",
            max_output_tokens=42,
        )

        self.assertEqual(response, "Swoop! Legacy client works.")
        post_mock.assert_called_once()

    def test_round_maker_get_shows_creator_selector_for_anonymous_users(self):
        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="round-creator"', html=False)
        self.assertContains(response, "Select a creator")

    def test_round_maker_get_hides_creator_selector_for_authenticated_users(self):
        user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(user)

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="round-creator"', html=False)
        self.assertContains(response, "Creator will be saved as Alex.")

    def test_round_maker_get_preserves_existing_conversation_history(self):
        session = self.client.session
        existing_history = [
            {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
            {"role": "user", "content": "I like science"},
            {"role": "assistant", "content": "Swoop! Try a weird botany round."},
        ]
        session["conversation_history"] = existing_history
        session.save()

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["conversation_history"], existing_history)

    def test_round_maker_get_uses_profile_conversation_history_for_authenticated_user(self):
        user = User.objects.create_user(username="alex", password="pw")
        user.profile.swoop_conversation_history = [
            {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
            {"role": "user", "content": "Keep this forever"},
            {"role": "assistant", "content": "Swoop! It is saved."},
        ]
        user.profile.save(update_fields=["swoop_conversation_history"])
        self.client.force_login(user)

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.session["conversation_history"],
            user.profile.swoop_conversation_history,
        )

    def test_round_maker_get_migrates_existing_session_history_into_profile(self):
        user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(user)
        existing_history = [
            {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
            {"role": "user", "content": "Move this into my profile"},
            {"role": "assistant", "content": "Swoop! Moved."},
        ]
        session = self.client.session
        session["conversation_history"] = existing_history
        session.save()

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.swoop_conversation_history, existing_history)

    @patch("GPTrivia.views._create_openai_text_response", return_value="Swoop! Try a fossils round.")
    @patch("GPTrivia.views._get_openai_client", return_value=object())
    def test_round_maker_post_appends_user_and_assistant_to_existing_history(self, _client_mock, response_mock):
        session = self.client.session
        session["conversation_history"] = [
            {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
            {"role": "user", "content": "I like science"},
            {"role": "assistant", "content": "Swoop! Try a weird botany round."},
        ]
        session.save()

        response = self.client.post(reverse("round_maker"), data={"user_input": "What about space?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"gpt_response": "Swoop! Try a fossils round."})
        conversation_history = self.client.session["conversation_history"]
        self.assertEqual(
            conversation_history[-2:],
            [
                {"role": "user", "content": "What about space?"},
                {"role": "assistant", "content": "Swoop! Try a fossils round."},
            ],
        )
        response_mock.assert_called_once()
        self.assertEqual(
            response_mock.call_args.kwargs["instructions"],
            views.SWOOP_SYSTEM_PROMPT,
        )

    @patch("GPTrivia.views._create_openai_text_response", return_value="Swoop! Try a fossils round.")
    @patch("GPTrivia.views._get_openai_client", return_value=object())
    def test_round_maker_post_persists_history_to_profile_for_authenticated_user(self, _client_mock, _response_mock):
        user = User.objects.create_user(username="alex", password="pw")
        user.profile.swoop_conversation_history = [
            {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
            {"role": "user", "content": "I like science"},
            {"role": "assistant", "content": "Swoop! Try a weird botany round."},
        ]
        user.profile.save(update_fields=["swoop_conversation_history"])
        self.client.force_login(user)

        response = self.client.post(reverse("round_maker"), data={"user_input": "What about space?"})

        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(
            user.profile.swoop_conversation_history[-2:],
            [
                {"role": "user", "content": "What about space?"},
                {"role": "assistant", "content": "Swoop! Try a fossils round."},
            ],
        )

    @patch(
        "GPTrivia.views._create_openai_text_response",
        return_value="Question: Which moon has methane lakes?\n\nAnswer: Titan",
    )
    @patch("GPTrivia.views._get_openai_client", return_value=object())
    def test_autogen_view_uses_direct_model_response(self, _client_mock, response_mock):
        response = self.client.post(
            reverse("autogen"),
            data={"user_input": "Space exploration round"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"autogen_response": "Question: Which moon has methane lakes?\n\nAnswer: Titan"},
        )
        self.assertEqual(
            response_mock.call_args.kwargs["instructions"],
            views.SWOOP_SAMPLE_QUESTION_PROMPT,
        )

    @patch("GPTrivia.views.share_slides")
    def test_share_view_uses_authenticated_username_for_creator(self, share_slides_mock):
        user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(user)

        response = self.client.post(
            reverse("share"),
            data={
                "presentation_id": "swoop-deck-123",
                "round_title": "Winged Science",
                "cooperative": "true",
                "creator": "Ignored",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        share_slides_mock.assert_called_once_with("swoop-deck-123")

        submitted_round = SubmittedRound.objects.get(presentation_id="swoop-deck-123")
        self.assertEqual(submitted_round.title, "Winged Science")
        self.assertEqual(submitted_round.creator, "Alex")
        self.assertTrue(submitted_round.cooperative)
        self.assertEqual(submitted_round.submitted_by, user)

    @patch("GPTrivia.views.share_slides")
    def test_share_view_requires_creator_for_anonymous_user(self, share_slides_mock):
        response = self.client.post(
            reverse("share"),
            data={
                "presentation_id": "anonymous-deck",
                "round_title": "Anonymous Round",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Creator is required.")
        share_slides_mock.assert_not_called()
        self.assertFalse(SubmittedRound.objects.filter(presentation_id="anonymous-deck").exists())

    @patch("GPTrivia.views.share_slides")
    def test_share_view_stores_creator_for_anonymous_user(self, share_slides_mock):
        response = self.client.post(
            reverse("share"),
            data={
                "presentation_id": "anonymous-deck",
                "round_title": "Anonymous Round",
                "creator": "Megan",
                "cooperative": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        share_slides_mock.assert_called_once_with("anonymous-deck")

        submitted_round = SubmittedRound.objects.get(presentation_id="anonymous-deck")
        self.assertEqual(submitted_round.creator, "Megan")
        self.assertTrue(submitted_round.cooperative)
        self.assertIsNone(submitted_round.submitted_by)
