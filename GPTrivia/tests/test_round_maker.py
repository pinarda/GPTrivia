from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia import mail
from GPTrivia import views
from GPTrivia.models import SubmittedRound


class RoundMakerTests(TestCase):
    class _FakeSlidesService:
        def __init__(self, get_payloads):
            self._get_payloads = list(get_payloads)
            self.batch_update_calls = []

        def presentations(self):
            return self

        def get(self, presentationId):
            payload = self._get_payloads.pop(0)
            return SimpleNamespace(execute=lambda: payload)

        def batchUpdate(self, presentationId, body):
            self.batch_update_calls.append({"presentationId": presentationId, "body": body})
            return SimpleNamespace(execute=lambda: {})

    def test_build_responses_input_marks_assistant_messages_as_output_text(self):
        response_input = views._build_responses_input(
            [
                {"role": "system", "content": views.SWOOP_SYSTEM_PROMPT},
                {"role": "user", "content": "Give me a round idea"},
                {"role": "assistant", "content": "Swoop! Try fossils."},
            ]
        )

        self.assertEqual(
            response_input,
            [
                {"role": "user", "content": [{"type": "input_text", "text": "Give me a round idea"}]},
                {"role": "assistant", "content": [{"type": "output_text", "text": "Swoop! Try fossils."}]},
            ],
        )

    def test_smart_template_slide_classifier_uses_explicit_question_and_answer_placeholders(self):
        question_slide = {
            "pageElements": [
                {
                    "shape": {
                        "text": {
                            "textElements": [
                                {"textRun": {"content": "ENTERTAINMENTQUESTION"}},
                            ]
                        }
                    }
                }
            ]
        }
        answer_slide = {
            "pageElements": [
                {
                    "shape": {
                        "text": {
                            "textElements": [
                                {"textRun": {"content": "ENTERTAINMENTANSWER"}},
                            ]
                        }
                    }
                }
            ]
        }

        self.assertEqual(
            mail._classify_smart_template_slide(question_slide),
            ("ENTERTAINMENT", "question"),
        )
        self.assertEqual(
            mail._classify_smart_template_slide(answer_slide),
            ("ENTERTAINMENT", "answer"),
        )

    def test_smart_template_slide_classifier_tolerates_whitespace_between_category_and_placeholder_suffix(self):
        question_slide = {
            "pageElements": [
                {
                    "shape": {
                        "text": {
                            "textElements": [
                                {"textRun": {"content": "SPORTS"}},
                                {"textRun": {"content": "\n"}},
                                {"textRun": {"content": "QUESTION"}},
                            ]
                        }
                    }
                }
            ]
        }
        answer_slide = {
            "pageElements": [
                {
                    "shape": {
                        "text": {
                            "textElements": [
                                {"textRun": {"content": "SPORTS"}},
                                {"textRun": {"content": " "}},
                                {"textRun": {"content": "ANSWER"}},
                            ]
                        }
                    }
                }
            ]
        }

        self.assertEqual(
            mail._classify_smart_template_slide(question_slide),
            ("SPORTS", "question"),
        )
        self.assertEqual(
            mail._classify_smart_template_slide(answer_slide),
            ("SPORTS", "answer"),
        )

    def test_resolve_smart_template_slide_map_falls_back_to_expected_slide_order(self):
        slides = [
            {"objectId": "cover", "pageElements": []},
            {"objectId": "intro", "pageElements": []},
        ]
        for category_name in mail.SMART_TRIVIAL_PURSUIT_CATEGORIES:
            slides.append({"objectId": f"q-{category_name.lower()}", "pageElements": []})
        slides.append(
            {
                "objectId": "answers-divider",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Answers"}},
                                ]
                            }
                        }
                    }
                ],
            }
        )
        for category_name in mail.SMART_TRIVIAL_PURSUIT_CATEGORIES:
            slides.append({"objectId": f"a-{category_name.lower()}", "pageElements": []})

        category_slide_map, first_category_index = mail._resolve_smart_template_slide_map(slides)

        self.assertEqual(first_category_index, 2)
        self.assertEqual(
            category_slide_map["SPORTS"],
            {"question": "q-sports", "answer": "a-sports"},
        )
        self.assertTrue(mail._smart_template_slide_map_is_complete(category_slide_map))

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
        self.assertFalse(post_mock.call_args.kwargs["json"]["store"])

    def test_openai_text_response_sets_store_false_for_sdk_client(self):
        class ResponsePayload:
            output_text = "Swoop! SDK client works."

        class ResponsesClient:
            def __init__(self):
                self.create_calls = []

            def create(self, **kwargs):
                self.create_calls.append(kwargs)
                return ResponsePayload()

        class ModernClient:
            def __init__(self):
                self.responses = ResponsesClient()

        client = ModernClient()

        response = views._create_openai_text_response(
            client=client,
            instructions="Test instructions",
            input_items="Test input",
            max_output_tokens=42,
        )

        self.assertEqual(response, "Swoop! SDK client works.")
        self.assertEqual(len(client.responses.create_calls), 1)
        self.assertFalse(client.responses.create_calls[0]["store"])

    def test_round_maker_get_shows_creator_selector_for_anonymous_users(self):
        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="round-creator"', html=False)
        self.assertNotContains(response, 'id="coop-choice-set"', html=False)
        self.assertContains(response, 'id="preview-button" disabled', html=False)
        self.assertContains(response, "Select a creator")
        self.assertContains(response, "Enter a round title and choose a creator to unlock preview.")

    def test_round_maker_get_hides_creator_selector_for_authenticated_users(self):
        user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(user)

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="round-creator"', html=False)
        self.assertNotContains(response, 'id="coop-choice-set"', html=False)
        self.assertContains(response, 'id="preview-button" disabled', html=False)
        self.assertContains(response, "Creator will be saved as Alex.")
        self.assertContains(response, "Enter a round title to unlock preview.")
        self.assertNotContains(response, "Trivial Pursuit (Smart)")

    def test_round_maker_get_shows_smart_template_for_opted_in_user(self):
        user = User.objects.create_user(username="alex", password="pw")
        user.profile.round_analysis_opt_in = True
        user.profile.save(update_fields=["round_analysis_opt_in"])
        self.client.force_login(user)

        response = self.client.get(reverse("round_maker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trivial Pursuit (Smart)")

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
        self.assertEqual(response_mock.call_args.kwargs["max_output_tokens"], 180)
        self.assertEqual(response_mock.call_args.kwargs["reasoning_effort"], "low")
        self.assertIn("exactly one challenging and off-the-wall trivia round idea", views.SWOOP_SYSTEM_PROMPT)

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
        self.assertEqual(response_mock.call_args.kwargs["max_output_tokens"], 220)
        self.assertEqual(response_mock.call_args.kwargs["reasoning_effort"], "low")

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

    @patch("GPTrivia.views.copy_template", return_value="smart-preview-123")
    @patch(
        "GPTrivia.views._classify_round_maker_smart_template",
        return_value=[
            {
                "question_number": 1,
                "question_text": "Which city is nicknamed the Big Apple?",
                "answer_text": "New York City",
                "category": "GEOGRAPHY",
            }
        ],
    )
    def test_preview_view_uses_smart_template_plan_for_opted_in_user(self, classify_mock, copy_template_mock):
        user = User.objects.create_user(username="alex", password="pw")
        user.profile.round_analysis_opt_in = True
        user.profile.save(update_fields=["round_analysis_opt_in"])
        self.client.force_login(user)

        response = self.client.post(
            reverse("preview"),
            data={
                "round_title": "Mixed Bag",
                "presentation_id": "1E0eNh79SX2ZNf-264wQERxPKFhgf2e2BAyrpSEJtyMw",
                "qas": '{"Question1":"Which city is nicknamed the Big Apple?","Answer1":"New York City"}',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"new_id": "smart-preview-123"})
        classify_mock.assert_called_once()
        self.assertEqual(
            copy_template_mock.call_args.kwargs["smart_category_plan"],
            [
                {
                    "question_number": 1,
                    "question_text": "Which city is nicknamed the Big Apple?",
                    "answer_text": "New York City",
                    "category": "GEOGRAPHY",
                }
            ],
        )

    @patch("GPTrivia.views.copy_template")
    def test_preview_view_rejects_smart_template_for_non_opted_in_user(self, copy_template_mock):
        user = User.objects.create_user(username="alex", password="pw")
        self.client.force_login(user)

        response = self.client.post(
            reverse("preview"),
            data={
                "round_title": "Mixed Bag",
                "presentation_id": "1E0eNh79SX2ZNf-264wQERxPKFhgf2e2BAyrpSEJtyMw",
                "qas": '{"Question1":"Which city is nicknamed the Big Apple?","Answer1":"New York City"}',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "This template requires round analysis opt-in.")
        copy_template_mock.assert_not_called()

    @patch("GPTrivia.mail._move_slide_to_index")
    @patch(
        "GPTrivia.mail._duplicate_slide_and_get_new_id",
        side_effect=["dup-question-1", "dup-question-2", "dup-answer-1", "dup-answer-2"],
    )
    @patch("GPTrivia.mail._find_smart_template_answers_insertion_index", return_value=8)
    @patch(
        "GPTrivia.mail._build_smart_template_slide_map",
        return_value=(
            {
                "GEOGRAPHY": {"question": "source-question-geo", "answer": "source-answer-geo"},
                "SCIENCE": {"question": "source-question-sci", "answer": "source-answer-sci"},
            },
            3,
        ),
    )
    def test_smart_template_places_answers_after_answer_divider_and_fills_question_text(
        self,
        _slide_map_mock,
        _answer_index_mock,
        duplicate_mock,
        move_mock,
    ):
        service = self._FakeSlidesService(
            [
                {
                    "slides": [
                        {"objectId": "intro-slide"},
                        {"objectId": "answers-divider"},
                    ]
                },
                {
                    "slides": [
                        {"objectId": "intro-slide"},
                        {"objectId": "answers-divider"},
                        {"objectId": "dup-question-1"},
                        {"objectId": "dup-question-2"},
                    ]
                },
            ]
        )

        mail._apply_smart_trivial_pursuit_layout(
            service,
            "smart-presentation-1",
            "Mixed Bag",
            [
                {
                    "category": "GEOGRAPHY",
                    "question_text": "Which city is nicknamed the Big Apple?",
                    "answer_text": "New York City",
                },
                {
                    "category": "SCIENCE",
                    "question_text": "Which planet has the most moons?",
                    "answer_text": "Saturn",
                },
            ],
        )

        self.assertEqual(
            [(call.args[2], call.args[3]) for call in move_mock.call_args_list],
            [
                ("dup-question-1", 3),
                ("dup-question-2", 4),
                ("dup-answer-1", 8),
                ("dup-answer-2", 9),
            ],
        )
        self.assertEqual(
            [call.args[2] for call in duplicate_mock.call_args_list],
            [
                "source-question-geo",
                "source-question-sci",
                "source-answer-geo",
                "source-answer-sci",
            ],
        )

        self.assertEqual(len(service.batch_update_calls), 1)
        request_batch = service.batch_update_calls[0]["body"]["requests"]

        replace_text_requests = [
            request["replaceAllText"]
            for request in request_batch
            if "replaceAllText" in request
        ]
        request_index = {
            (
                request["pageObjectIds"][0],
                request["containsText"]["text"],
            ): request["replaceText"]
            for request in replace_text_requests
            if request.get("pageObjectIds")
        }

        self.assertEqual(
            request_index[("dup-answer-1", "GEOGRAPHYQUESTION")],
            "Which city is nicknamed the Big Apple?",
        )
        self.assertEqual(
            request_index[("dup-answer-1", "GEOGRAPHYANSWER")],
            "New York City",
        )
        self.assertEqual(
            request_index[("dup-answer-2", "SCIENCEQUESTION")],
            "Which planet has the most moons?",
        )
        self.assertEqual(
            request_index[("dup-answer-2", "SCIENCEANSWER")],
            "Saturn",
        )
