import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.mail import PresentationBuildError
from GPTrivia.models import GPTriviaRound, HomePresentationBuildJob, MergedPresentation, PresentationBuildState, SubmittedRound


class HomeViewPresentationSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="test-pass")
        self.client.force_login(self.user)
        self._create_round(date=datetime.date(2026, 3, 5), round_number=1, title="Round A", creator="Alex")
        self._create_round(date=datetime.date(2026, 3, 12), round_number=1, title="Round B", creator="Megan")
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

    def _create_round(self, *, date, round_number, title, creator):
        return GPTriviaRound.objects.create(
            creator=creator,
            title=title,
            major_category="",
            minor_category1="",
            minor_category2="",
            date=date,
            round_number=round_number,
            max_score=10,
            cooperative=False,
            link=f"https://example.com/{title.casefold().replace(' ', '-')}",
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

    def test_home_ignores_blank_presentation_ids_for_selection_and_calendar(self):
        self._create_presentation(
            name="03.14.2026",
            presentation_id="",
            round_names=["Blank Placeholder"],
            creator_list=["Alex"],
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_presentation_id"], "presentation-latest")
        self.assertNotIn("2026-03-14", response.context["presentation_calendar"])

    def test_home_ignores_presentations_without_rounds_for_selection_and_calendar(self):
        stale_presentation = self._create_presentation(
            name="03.16.2026",
            presentation_id="presentation-stale",
            round_names=["Stale Round"],
            creator_list=["Alex"],
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_presentation_id"], "presentation-latest")
        self.assertNotIn("2026-03-16", response.context["presentation_calendar"])
        self.assertFalse(MergedPresentation.objects.filter(id=stale_presentation.id).exists())

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

    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.create_presentation", return_value="presentation-generated")
    def test_generate_ajax_queues_new_presentation(self, create_mock, worker_mock):
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

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertTrue(payload["build_queued"])
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["action"], "generate")
        self.assertEqual(payload["presentation_name"], "6.05.2026")
        create_mock.assert_not_called()
        worker_mock.assert_called_once()
        queued_job = HomePresentationBuildJob.objects.get()
        self.assertEqual(queued_job.action, HomePresentationBuildJob.ACTION_GENERATE)
        self.assertEqual(queued_job.presentation_name, "6.05.2026")
        self.assertEqual(queued_job.round_payload[0]["title"], "Round C")

    @patch("GPTrivia.views._broadcast_home_build_result")
    @patch("GPTrivia.views._broadcast_home_presentation_refresh")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.create_presentation", return_value="presentation-generated")
    def test_generate_marks_matching_submitted_round_consumed(self, create_mock, _worker_mock, _refresh_mock, _result_mock):
        submitted_round = SubmittedRound.objects.create(
            presentation_id="swoop-123",
            title="Round C",
            creator="Alex",
            cooperative=False,
            link="https://docs.google.com/presentation/d/swoop-123/edit",
            is_consumed=False,
        )

        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 6, 5)):
            response = self.client.post(
                reverse("home"),
                data={
                    "action": "generate",
                    "round_order_0": "1",
                    "round_title_0": "Round C",
                    "round_creator_0": "Alex",
                    "round_link_0": "https://docs.google.com/presentation/d/swoop-123/edit",
                    "round_old_link_0": "https://docs.google.com/presentation/d/swoop-123/edit",
                    "round_shared_date_0": "03.12.2026",
                },
            )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        _run_home_presentation_build_job(job.id)
        create_mock.assert_called_once()
        submitted_round.refresh_from_db()
        self.assertTrue(submitted_round.is_consumed)

    @patch("GPTrivia.views._broadcast_home_build_result")
    @patch("GPTrivia.views._broadcast_home_presentation_refresh")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch(
        "GPTrivia.views.create_presentation",
        return_value=(
            "presentation-generated",
            ["Alex"],
            ["Converted PowerPoint Round"],
            ["https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.round"],
        ),
    )
    def test_generate_passes_original_pptx_link_to_email_read_marker(
        self,
        create_mock,
        _worker_mock,
        _refresh_mock,
        _result_mock,
    ):
        converted_link = "https://docs.google.com/presentation/d/converted-pptx/edit"
        source_link = "https://docs.google.com/presentation/d/original-pptx/edit?usp=drive_web"
        submitted_round = SubmittedRound.objects.create(
            presentation_id="converted-pptx",
            gmail_message_id="gmail-converted-pptx",
            title="Converted PowerPoint Round",
            source_title="Converted PowerPoint Round",
            creator="Alex",
            source_creator="Zach",
            link=converted_link,
            source_link=source_link,
            is_consumed=False,
            is_currently_available=True,
        )

        response = self.client.post(
            reverse("home"),
            data={
                "action": "generate",
                "round_order_0": "1",
                "round_title_0": "Edited PowerPoint Round",
                "round_source_title_0": submitted_round.source_title,
                "round_creator_0": "Megan",
                "round_source_creator_0": submitted_round.source_creator,
                "round_link_0": converted_link,
                "round_old_link_0": source_link,
                "round_presentation_id_0": submitted_round.presentation_id,
                "round_gmail_message_id_0": submitted_round.gmail_message_id,
                "round_shared_date_0": "06.13.2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        _run_home_presentation_build_job(job.id)

        self.assertEqual(create_mock.call_args.kwargs["old_links"], [source_link])
        self.assertEqual(
            create_mock.call_args.kwargs["gmail_message_ids"],
            ["gmail-converted-pptx"],
        )
        submitted_round.refresh_from_db()
        self.assertTrue(submitted_round.is_consumed)
        self.assertFalse(submitted_round.is_currently_available)

    @patch("GPTrivia.views._broadcast_home_build_result")
    @patch("GPTrivia.views._broadcast_home_presentation_refresh")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
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
    def test_generate_job_records_partial_presentation_on_failure(self, _create_mock, _worker_mock, _refresh_mock, _result_mock):
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

        self.assertEqual(response.status_code, 202)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        with self.assertRaises(PresentationBuildError):
            _run_home_presentation_build_job(job.id, raise_on_error=True)
        job.refresh_from_db()
        self.assertEqual(job.status, HomePresentationBuildJob.STATUS_FAILED)
        failed_presentation = MergedPresentation.objects.get(presentation_id="presentation-partial")
        self.assertEqual(failed_presentation.status, MergedPresentation.STATUS_FAILED)
        self.assertEqual(
            failed_presentation.error_message,
            "Slide generation stopped before completion: simulated failure",
        )

    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old-updated", ["Jenny"], ["Round D"], ["https://example.com/round-d"]))
    def test_update_ajax_queues_selected_presentation(self, update_mock, worker_mock):
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

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertTrue(payload["build_queued"])
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["action"], "update")
        self.assertEqual(payload["presentation_name"], "3.05.2026")
        update_mock.assert_not_called()
        worker_mock.assert_called_once()
        queued_job = HomePresentationBuildJob.objects.get()
        self.assertEqual(queued_job.action, HomePresentationBuildJob.ACTION_UPDATE)
        self.assertEqual(queued_job.selected_presentation_id, self.older_presentation.presentation_id)
        self.older_presentation.refresh_from_db()
        self.assertEqual(self.older_presentation.presentation_id, "presentation-old")

    @patch("GPTrivia.views._broadcast_home_build_result")
    @patch("GPTrivia.views._broadcast_home_presentation_refresh")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old-updated", ["Jenny"], ["Round D"], ["https://example.com/round-d"]))
    def test_update_marks_matching_submitted_round_consumed(self, update_mock, _worker_mock, _refresh_mock, _result_mock):
        submitted_round = SubmittedRound.objects.create(
            presentation_id="swoop-123",
            title="Round C",
            creator="Alex",
            cooperative=False,
            link="https://docs.google.com/presentation/d/swoop-123/edit",
            is_consumed=False,
        )

        response = self.client.post(
            reverse("home"),
            data={
                "action": "update",
                "selected_presentation_id": self.older_presentation.presentation_id,
                "round_order_0": "1",
                "round_title_0": "Round C",
                "round_creator_0": "Alex",
                "round_link_0": "https://docs.google.com/presentation/d/swoop-123/edit",
                "round_old_link_0": "https://docs.google.com/presentation/d/swoop-123/edit",
                "round_shared_date_0": "03.12.2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        _run_home_presentation_build_job(job.id)
        update_mock.assert_called_once()
        submitted_round.refresh_from_db()
        self.assertTrue(submitted_round.is_consumed)

    @patch("GPTrivia.views._broadcast_home_build_result")
    @patch("GPTrivia.views._broadcast_home_presentation_refresh")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old-updated", ["Jenny"], ["Round D"], ["https://example.com/round-d"]))
    def test_update_appends_new_round_after_existing_scoresheet_rounds(self, _update_mock, _worker_mock, _refresh_mock, _result_mock):
        presentation_date = datetime.date(2026, 3, 5)
        self._create_round(date=presentation_date, round_number=2, title="Round B", creator="Megan")
        self._create_round(date=presentation_date, round_number=3, title="Round C", creator="Zach")
        self.older_presentation.round_names = ["Round A", "Round B", "Round C"]
        self.older_presentation.creator_list = ["Alex", "Megan", "Zach"]
        self.older_presentation.save(update_fields=["round_names", "creator_list"])

        response = self.client.post(
            reverse("home"),
            data={
                "action": "update",
                "selected_presentation_id": self.older_presentation.presentation_id,
                "round_order_0": "1",
                "round_title_0": "Round D",
                "round_creator_0": "Jenny",
                "round_link_0": "https://example.com/round-d",
                "round_old_link_0": "https://example.com/round-d/edit",
                "round_shared_date_0": "03.12.2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        _run_home_presentation_build_job(job.id)
        new_round = GPTriviaRound.objects.get(title="Round D", date=presentation_date)
        self.assertEqual(new_round.round_number, 4)
        self.assertEqual(
            list(
                GPTriviaRound.objects.filter(date=presentation_date)
                .order_by("round_number")
                .values_list("title", flat=True)
            ),
            ["Round A", "Round B", "Round C", "Round D"],
        )

    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.update_merged_presentation", return_value=("presentation-old", [], [], []))
    def test_update_uses_selected_presentation_id(self, update_mock, _worker_mock):
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
        self.assertEqual(response.url, reverse("home"))
        update_mock.assert_not_called()
        queued_job = HomePresentationBuildJob.objects.get()
        self.assertEqual(queued_job.selected_presentation_id, self.older_presentation.presentation_id)

    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    @patch("GPTrivia.views.create_presentation", return_value="presentation-generated")
    def test_generate_non_ajax_keeps_redirect_fallback(self, create_mock, _worker_mock):
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
        create_mock.assert_not_called()
        self.assertEqual(HomePresentationBuildJob.objects.count(), 1)

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
