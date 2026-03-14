import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.mail import PresentationBuildError
from GPTrivia.models import MergedPresentation, PresentationBuildState


class HomeViewPresentationSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="test-pass")
        self.client.force_login(self.user)
        self.older_presentation = self._create_presentation(
            name="3.05.2026",
            presentation_id="presentation-old",
            round_names=["Round A"],
            creator_list=["Alex"],
        )
        self.latest_presentation = self._create_presentation(
            name="03.12.2026",
            presentation_id="presentation-latest",
            round_names=["Round B"],
            creator_list=["Megan"],
        )

    def _create_presentation(self, name, presentation_id, round_names, creator_list):
        return MergedPresentation.objects.create(
            name=name,
            presentation_id=presentation_id,
            round_names=round_names,
            creator_list=creator_list,
            player_list={},
            host="Alex",
            scorekeeper="Megan",
            style_points={},
            notes="",
            tiebreak_winner="",
        )

    def test_home_defaults_to_latest_presentation_and_calendar_context(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["presentation_url"],
            "https://docs.google.com/presentation/d/presentation-latest/embed",
        )
        self.assertEqual(response.context["selected_presentation_id"], "presentation-latest")
        self.assertEqual(response.context["selected_presentation_iso_date"], "2026-03-12")
        self.assertEqual(
            response.context["presentation_calendar"],
            {
                "2026-03-05": {
                    "presentation_id": "presentation-old",
                    "name": "3.05.2026",
                },
                "2026-03-12": {
                    "presentation_id": "presentation-latest",
                    "name": "03.12.2026",
                },
            },
        )
        self.assertContains(response, 'id="calendar-button"')

    def test_home_uses_requested_presentation_id_for_embed(self):
        response = self.client.get(
            reverse("home"),
            {"presentation_id": self.older_presentation.presentation_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["presentation_url"],
            "https://docs.google.com/presentation/d/presentation-old/embed",
        )
        self.assertEqual(response.context["selected_presentation_id"], "presentation-old")
        self.assertEqual(response.context["selected_presentation_iso_date"], "2026-03-05")

    def test_home_invalid_presentation_id_falls_back_to_latest(self):
        response = self.client.get(reverse("home"), {"presentation_id": "missing-presentation"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_presentation_id"], "presentation-latest")
        self.assertEqual(
            response.context["presentation_url"],
            "https://docs.google.com/presentation/d/presentation-latest/embed",
        )

    def test_home_ignores_failed_presentations_for_default_selection(self):
        self._create_presentation(
            name="03.13.2026",
            presentation_id="presentation-failed",
            round_names=["Round Failed"],
            creator_list=["Alex"],
        )
        MergedPresentation.objects.filter(presentation_id="presentation-failed").update(
            status=MergedPresentation.STATUS_FAILED,
            error_message="generation failed",
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_presentation_id"], "presentation-latest")

    def test_home_context_includes_active_build_state(self):
        PresentationBuildState.objects.create(
            key="home_page",
            is_active=True,
            action="generate",
            presentation_name="3.14.2026",
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["home_build_state"],
            {
                "is_active": True,
                "action": "generate",
                "presentation_name": "3.14.2026",
                "presentation_id": "",
            },
        )

    @patch("GPTrivia.views._schedule_home_presentation_refresh_broadcast")
    @patch("GPTrivia.views.create_presentation", return_value="presentation-generated")
    def test_generate_ajax_returns_json_for_new_presentation(self, create_mock, refresh_broadcast_mock):
        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 6, 5)):
            response = self.client.post(
                reverse("home"),
                data={
                    "action": "generate",
                    "round_order_0": "1",
                    "round_title_0": "Round C",
                    "round_creator_0": "Alex",
                    "round_link_0": "https://example.com/round-c",
                    "round_old_link_0": "https://example.com/round-c/edit",
                    "round_shared_date_0": "03.12.2026",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            create_mock.call_args.kwargs["presentation_name"],
            "6.05.2026",
        )
        self.assertEqual(
            response.json(),
            {
                "presentation_id": "presentation-generated",
                "presentation_name": "6.05.2026",
                "presentation_url": "https://docs.google.com/presentation/d/presentation-generated/embed",
                "selected_presentation_iso_date": "2026-06-05",
                "calendar_entry": {
                    "presentation_id": "presentation-generated",
                    "name": "6.05.2026",
                },
            },
        )
        generated_presentation = MergedPresentation.objects.get(presentation_id="presentation-generated")
        self.assertEqual(generated_presentation.notes, "")
        self.assertEqual(generated_presentation.status, MergedPresentation.STATUS_READY)
        refresh_broadcast_mock.assert_called_once()
        self.assertEqual(refresh_broadcast_mock.call_args.kwargs["action"], "generate")
        self.assertEqual(refresh_broadcast_mock.call_args.args[1], "presentation-generated")

    @patch(
        "GPTrivia.views.create_presentation",
        side_effect=PresentationBuildError(
            "Slide generation stopped before completion: simulated failure",
            presentation_id="presentation-partial",
            creators=["Alex"],
            round_titles=["Round C"],
            round_links=["https://docs.google.com/presentation/d/presentation-partial/edit#slide=id.partial"],
        ),
    )
    def test_generate_ajax_returns_partial_presentation_payload_on_failure(self, _create_mock):
        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 6, 5)):
            response = self.client.post(
                reverse("home"),
                data={
                    "action": "generate",
                    "round_order_0": "1",
                    "round_title_0": "Round C",
                    "round_creator_0": "Alex",
                    "round_link_0": "https://example.com/round-c",
                    "round_old_link_0": "https://example.com/round-c/edit",
                    "round_shared_date_0": "03.12.2026",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "presentation_id": "presentation-partial",
                "presentation_name": "6.05.2026",
                "presentation_url": "https://docs.google.com/presentation/d/presentation-partial/embed",
                "selected_presentation_iso_date": "2026-06-05",
                "calendar_entry": None,
                "detail": "Slide generation stopped before completion: simulated failure",
                "build_failed": True,
            },
        )
        failed_presentation = MergedPresentation.objects.get(presentation_id="presentation-partial")
        self.assertEqual(failed_presentation.status, MergedPresentation.STATUS_FAILED)
        self.assertEqual(
            failed_presentation.error_message,
            "Slide generation stopped before completion: simulated failure",
        )

    @patch("GPTrivia.views._schedule_home_presentation_refresh_broadcast")
    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old-updated", ["Jenny"], ["Round D"], ["https://example.com/round-d"]))
    def test_update_ajax_returns_json_for_selected_presentation(self, update_mock, refresh_broadcast_mock):
        response = self.client.post(
            reverse("home"),
            data={
                "action": "update",
                "selected_presentation_id": self.older_presentation.presentation_id,
                "round_order_0": "1",
                "round_title_0": "Round C",
                "round_creator_0": "Alex",
                "round_link_0": "https://example.com/round-c",
                "round_old_link_0": "https://example.com/round-c/edit",
                "round_shared_date_0": "03.12.2026",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(update_mock.call_args.args[0], self.older_presentation.presentation_id)
        self.older_presentation.refresh_from_db()
        self.assertEqual(self.older_presentation.presentation_id, "presentation-old-updated")
        self.assertEqual(
            response.json(),
            {
                "presentation_id": "presentation-old-updated",
                "presentation_name": "3.05.2026",
                "presentation_url": "https://docs.google.com/presentation/d/presentation-old-updated/embed",
                "selected_presentation_iso_date": "2026-03-05",
                "calendar_entry": {
                    "presentation_id": "presentation-old-updated",
                    "name": "3.05.2026",
                },
            },
        )
        refresh_broadcast_mock.assert_called_once()
        self.assertEqual(refresh_broadcast_mock.call_args.kwargs["action"], "update")
        self.assertEqual(refresh_broadcast_mock.call_args.args[1], "presentation-old-updated")

    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old", [], [], []))
    def test_update_uses_selected_presentation_id(self, update_mock):
        response = self.client.post(
            reverse("home"),
            data={
                "action": "update",
                "selected_presentation_id": self.older_presentation.presentation_id,
                "round_order_0": "1",
                "round_title_0": "Round C",
                "round_creator_0": "Alex",
                "round_link_0": "https://example.com/round-c",
                "round_old_link_0": "https://example.com/round-c/edit",
                "round_shared_date_0": "03.12.2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('home')}?presentation_id={self.older_presentation.presentation_id}",
        )
        self.assertEqual(update_mock.call_args.args[0], self.older_presentation.presentation_id)
        self.assertEqual(update_mock.call_args.args[1], ["Alex"])

    @patch("GPTrivia.views.create_presentation", return_value="presentation-generated")
    def test_generate_non_ajax_keeps_redirect_fallback(self, _create_mock):
        response = self.client.post(
            reverse("home"),
            data={
                "action": "generate",
                "round_order_0": "1",
                "round_title_0": "Round C",
                "round_creator_0": "Alex",
                "round_link_0": "https://example.com/round-c",
                "round_old_link_0": "https://example.com/round-c/edit",
                "round_shared_date_0": "03.12.2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    @patch("GPTrivia.views.create_presentation")
    def test_generate_ajax_rejects_when_build_is_already_in_progress(self, create_mock):
        PresentationBuildState.objects.create(
            key="home_page",
            is_active=True,
            action="update",
            presentation_name="3.14.2026",
            presentation_id="presentation-busy",
        )

        response = self.client.post(
            reverse("home"),
            data={
                "action": "generate",
                "round_order_0": "1",
                "round_title_0": "Round C",
                "round_creator_0": "Alex",
                "round_link_0": "https://example.com/round-c",
                "round_old_link_0": "https://example.com/round-c/edit",
                "round_shared_date_0": "03.12.2026",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {
                "detail": "Another presentation build is already in progress.",
                "build_in_progress": True,
                "is_active": True,
                "action": "update",
                "presentation_name": "3.14.2026",
                "presentation_id": "presentation-busy",
            },
        )
        create_mock.assert_not_called()
