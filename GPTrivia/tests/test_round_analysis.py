import io
import zipfile
import datetime
import os
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from GPTrivia.models import GPTriviaRound, HomePresentationBuildJob, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun
from GPTrivia.round_analysis import (
    ROUND_ANALYSIS_AUTO_DELAY_SECONDS,
    ROUND_ANALYSIS_STALE_RUNNING_SECONDS,
    _apply_apps_script_media_links,
    _analyze_round_slides,
    _build_possible_answers,
    _build_possible_answers_with_aliases,
    _claim_next_due_round_analysis_run_id,
    _classify_round_structure,
    _extract_picture_grid_questions_by_layout,
    _extract_embedded_slide_media_assets,
    _extract_slide_line_items,
    _extract_slide_media_items,
    _fetch_slide_thumbnail_data_url,
    _fetch_url_with_retries,
    _generate_additional_possible_answer_aliases,
    _is_placeholder_media_url,
    _normalize_analysis_categories,
    _normalize_analysis_questions,
    _optimize_analysis_image_content,
    _store_round_analysis,
    queue_round_analysis_batch,
)


class RoundAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="Alex", password="pw")
        self.user.profile.round_analysis_opt_in = True
        self.user.profile.save(update_fields=["round_analysis_opt_in"])
        self.client.force_login(self.user)

    @patch(
        "GPTrivia.views.create_presentation",
        return_value=(
            "presentation-generated",
            ["Alex", "Megan"],
            ["Fresh Round", "Historic Round"],
            [
                "https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.fresh",
                "https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.historic",
            ],
        ),
    )
    @patch("GPTrivia.round_analysis.schedule_auto_round_analysis_batch")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    def test_home_generate_auto_queues_only_new_rounds(self, _worker_mock, queue_mock, create_mock):
        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 3, 20)):
            with patch("GPTrivia.views._broadcast_home_build_state"):
                with patch("GPTrivia.views._broadcast_home_presentation_refresh"):
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.post(
                            reverse("home"),
                            data={
                                "action": "generate",
                                "round_order_0": "1",
                                "round_title_0": "Fresh Round",
                                "round_creator_0": "Alex",
                                "round_link_0": "https://docs.google.com/presentation/d/source-fresh/edit",
                                "round_old_link_0": "https://docs.google.com/presentation/d/source-fresh/edit",
                                "round_shared_date_0": "2026-03-19",
                                "round_is_new_0": "1",
                                "round_order_1": "2",
                                "round_title_1": "Historic Round",
                                "round_creator_1": "Megan",
                                "round_link_1": "https://docs.google.com/presentation/d/source-historic/edit#slide=id.old",
                                "round_old_link_1": "https://docs.google.com/presentation/d/source-historic/edit#slide=id.old",
                                "round_shared_date_1": "2025-05-26",
                                "round_is_new_1": "0",
                            },
                        )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        with patch("GPTrivia.views._broadcast_home_build_state"):
            with patch("GPTrivia.views._broadcast_home_presentation_refresh"):
                with patch("GPTrivia.views._broadcast_home_build_result"):
                    _run_home_presentation_build_job(job.id)
        self.assertEqual(create_mock.call_count, 1)
        created_rounds = list(GPTriviaRound.objects.order_by("round_number", "id"))
        self.assertEqual([round_obj.title for round_obj in created_rounds], ["Fresh Round", "Historic Round"])
        queue_mock.assert_called_once()
        queued_ids = queue_mock.call_args.args[0]
        self.assertEqual(queued_ids, [created_rounds[0].id])
        self.assertEqual(queue_mock.call_args.kwargs["initiated_by"], "Alex")

    @patch(
        "GPTrivia.views.create_presentation",
        return_value=(
            "presentation-generated",
            ["Alex Smith"],
            ["Fresh Round"],
            [
                "https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.fresh",
            ],
        ),
    )
    @patch("GPTrivia.round_analysis.schedule_auto_round_analysis_batch")
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    def test_home_generate_logs_creator_opt_in_skip_reason_for_auto_analysis(self, _worker_mock, queue_mock, create_mock):
        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 3, 20)):
            with patch("GPTrivia.views._broadcast_home_build_state"):
                with patch("GPTrivia.views._broadcast_home_presentation_refresh"):
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.post(
                            reverse("home"),
                            data={
                                "action": "generate",
                                "round_order_0": "1",
                                "round_title_0": "Fresh Round",
                                "round_creator_0": "Alex Smith",
                                "round_link_0": "https://docs.google.com/presentation/d/source-fresh/edit",
                                "round_old_link_0": "https://docs.google.com/presentation/d/source-fresh/edit",
                                "round_shared_date_0": "2026-03-19",
                                "round_is_new_0": "1",
                            },
                        )

        self.assertEqual(response.status_code, 302)
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        with self.assertLogs("GPTrivia.views", level="INFO") as captured_logs:
            with patch("GPTrivia.views._broadcast_home_build_state"):
                with patch("GPTrivia.views._broadcast_home_presentation_refresh"):
                    with patch("GPTrivia.views._broadcast_home_build_result"):
                        _run_home_presentation_build_job(job.id)
        self.assertEqual(create_mock.call_count, 1)
        queue_mock.assert_not_called()
        joined_logs = "\n".join(captured_logs.output)
        self.assertIn("Auto round analysis skipped", joined_logs)
        self.assertIn("reason=creator_not_opted_in", joined_logs)

    @patch("GPTrivia.round_analysis.ensure_round_analysis_worker_running")
    def test_queue_round_analysis_batch_sets_delayed_schedule_for_auto_runs(self, worker_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Delayed Analysis Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        before_queue = datetime.datetime.now(datetime.timezone.utc)
        queued_run_ids = queue_round_analysis_batch(
            [round_obj.id],
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_AUTO,
            initiated_by="Alex",
            batch_label="new rounds from 03.20.2026",
            delay_seconds=ROUND_ANALYSIS_AUTO_DELAY_SECONDS,
        )
        after_queue = datetime.datetime.now(datetime.timezone.utc)

        self.assertEqual(len(queued_run_ids), 1)
        worker_mock.assert_called_once()
        queued_run = RoundQuestionAnalysisRun.objects.get(id=queued_run_ids[0])
        expected_minimum = before_queue + datetime.timedelta(seconds=ROUND_ANALYSIS_AUTO_DELAY_SECONDS)
        expected_maximum = after_queue + datetime.timedelta(seconds=ROUND_ANALYSIS_AUTO_DELAY_SECONDS)
        self.assertGreaterEqual(queued_run.scheduled_for, expected_minimum)
        self.assertLessEqual(queued_run.scheduled_for, expected_maximum)
        self.assertEqual(queued_run.batch_label, "new rounds from 03.20.2026")
        self.assertTrue(queued_run.batch_key)

    def test_claim_next_due_round_analysis_run_id_recovers_stale_running_run(self):
        blocked_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Blocked Analysis Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        pending_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Pending Analysis Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        stale_run = RoundQuestionAnalysisRun.objects.create(
            round=blocked_round,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
            started_at=timezone.now() - datetime.timedelta(seconds=ROUND_ANALYSIS_STALE_RUNNING_SECONDS + 30),
        )
        RoundQuestionAnalysisRun.objects.filter(id=stale_run.id).update(
            updated_at=timezone.now() - datetime.timedelta(seconds=ROUND_ANALYSIS_STALE_RUNNING_SECONDS + 30)
        )
        pending_run = RoundQuestionAnalysisRun.objects.create(
            round=pending_round,
            status=RoundQuestionAnalysisRun.STATUS_PENDING,
            scheduled_for=timezone.now() - datetime.timedelta(seconds=5),
        )

        claimed_run_id = _claim_next_due_round_analysis_run_id()

        self.assertEqual(claimed_run_id, pending_run.id)
        stale_run.refresh_from_db()
        pending_run.refresh_from_db()
        self.assertEqual(stale_run.status, RoundQuestionAnalysisRun.STATUS_FAILED)
        self.assertIn("stopped heartbeating", stale_run.error_message)
        self.assertEqual(pending_run.status, RoundQuestionAnalysisRun.STATUS_RUNNING)

    def test_trigger_round_analysis_rejects_replay_round(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Replay Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=True,
            cooperative=False,
            link="https://docs.google.com/presentation/d/replay-round/edit#slide=id.r1",
        )

        response = self.client.post(reverse("trigger_round_analysis", args=[round_obj.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(RoundQuestionAnalysisRun.objects.exists())

    def test_trigger_round_analysis_rejects_creator_without_opt_in(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="No Opt In Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/no-opt-in/edit#slide=id.r1",
        )

        response = self.client.post(reverse("trigger_round_analysis", args=[round_obj.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(RoundQuestionAnalysisRun.objects.exists())

    @patch("GPTrivia.round_analysis.queue_round_analysis", return_value=[456])
    def test_trigger_round_analysis_allows_round_with_existing_completed_analysis(self, queue_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Already Analyzed",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/already-analyzed/edit#slide=id.r1",
        )
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )

        response = self.client.post(reverse("trigger_round_analysis", args=[round_obj.id]))

        self.assertEqual(response.status_code, 302)
        queue_mock.assert_called_once_with(
            round_obj.id,
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
            initiated_by="Alex",
        )

    @patch("GPTrivia.round_analysis.queue_round_analysis", return_value=[123])
    def test_trigger_round_analysis_returns_json_for_ajax(self, queue_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Ajax Analyze",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/ajax-analyze/edit#slide=id.r1",
        )

        with patch(
            "GPTrivia.views._build_round_analysis_status_map",
            return_value={
                round_obj.id: {
                    "status": "pending",
                    "status_label": "Pending",
                    "has_any_run": True,
                    "is_active": True,
                    "button_label": "Analyze",
                    "button_disabled": True,
                    "show_already_analyzed": False,
                    "has_completed_entries": False,
                    "view_url": "",
                }
            },
        ):
            response = self.client.post(
                reverse("trigger_round_analysis", args=[round_obj.id]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"]["status"], "pending")
        queue_mock.assert_called_once_with(
            round_obj.id,
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
            initiated_by="Alex",
        )

    @patch("GPTrivia.round_analysis.queue_round_analysis", return_value=[123])
    def test_trigger_round_analysis_queues_non_replay_round(self, queue_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Fresh Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/fresh-round/edit#slide=id.r1",
        )

        response = self.client.post(reverse("trigger_round_analysis", args=[round_obj.id]))

        self.assertEqual(response.status_code, 302)
        queue_mock.assert_called_once_with(
            round_obj.id,
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
            initiated_by="Alex",
        )

    def test_round_analysis_page_renders_latest_completed_entries(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Analyzer Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/analyzer-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
            notes="Detected a picture round.",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Name this nebula.",
            instruction_text="Identify the pictured nebula.",
            answer_text="Crab Nebula",
            round_type="picture",
            media_kind="image",
            media_url="https://example.com/image.png",
            source_slide_number=2,
            source_slide_url="https://docs.google.com/presentation/d/source-deck/edit#slide=id.slide2",
            notes="Detected a picture round.",
            major_category="Science",
            minor_category1="Astronomy",
            minor_category2="Images",
            player_correctness={"Alex": "", "Megan": ""},
        )

        response = self.client.get(reverse("round_analysis_list"), {"round_id": round_obj.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analyzer Round")
        self.assertContains(response, "Name this nebula.")
        self.assertContains(response, "Identify the pictured nebula.")
        self.assertContains(response, "Crab Nebula")
        self.assertContains(response, "Open linked image")
        self.assertContains(response, "Open source slide")

    def test_round_analysis_status_returns_latest_payload(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Status Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/status-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Status question",
            answer_text="Status answer",
            round_type="picture",
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_status", args=[round_obj.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["status"]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["button_label"], "Analyze Again")
        self.assertTrue(payload["show_already_analyzed"])
        self.assertTrue(payload["has_completed_entries"])
        self.assertIn(f"round_id={round_obj.id}", payload["view_url"])
        self.assertTrue(payload["can_trigger"])
        self.assertEqual(payload["error_summary"], "")
        self.assertEqual(payload["error_message"], "")

    def test_round_analysis_status_running_exposes_restart_button(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Running Status Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/status-round-running/edit#slide=id.r1",
        )
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
            round_type="picture",
        )

        response = self.client.get(reverse("round_analysis_status", args=[round_obj.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["status"]
        self.assertEqual(payload["status"], "running")
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["button_label"], "Restart")
        self.assertEqual(payload["button_action"], "restart")
        self.assertFalse(payload["button_disabled"])

    @patch("GPTrivia.round_analysis.ensure_round_analysis_worker_running")
    def test_round_analysis_status_pending_auto_exposes_scheduled_summary_and_nudges_worker(self, worker_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Scheduled Status Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/status-round-pending/edit#slide=id.r1",
        )
        scheduled_for = timezone.now() + datetime.timedelta(minutes=5)
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_PENDING,
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_AUTO,
            scheduled_for=scheduled_for,
            round_type="picture",
        )

        response = self.client.get(reverse("round_analysis_status", args=[round_obj.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["status"]
        self.assertEqual(payload["status"], "pending")
        self.assertTrue(payload["scheduled_summary"].startswith("Auto queued for "))
        self.assertEqual(payload["scheduled_for_iso"], scheduled_for.isoformat())
        worker_mock.assert_called()

    def test_round_analysis_status_includes_failure_detail(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Failed Status Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/status-round-failed/edit#slide=id.r1",
        )
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_FAILED,
            error_message="Missing slide notes for slide 3\n\nTraceback line 1\nTraceback line 2",
        )

        response = self.client.get(reverse("round_analysis_status", args=[round_obj.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["status"]
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["status_label"], "Failed")
        self.assertEqual(payload["error_summary"], "Missing slide notes for slide 3")
        self.assertIn("Traceback line 1", payload["error_message"])

    @patch("GPTrivia.round_analysis.queue_round_analysis")
    def test_restart_round_analysis_marks_active_run_failed_and_requeues(self, queue_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Restartable Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/restartable-round/edit#slide=id.r1",
        )
        active_run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
            round_type="picture",
        )
        queued_run = None

        def create_pending_run(*args, **kwargs):
            nonlocal queued_run
            queued_run = RoundQuestionAnalysisRun.objects.create(
                round=round_obj,
                status=RoundQuestionAnalysisRun.STATUS_PENDING,
            )
            return [queued_run.id]

        queue_mock.side_effect = create_pending_run

        response = self.client.post(
            reverse("restart_round_analysis", args=[round_obj.id]),
            {"next": reverse("rounds_list")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"]["status"], "pending")
        self.assertEqual(payload["status"]["button_label"], "Restart")
        self.assertEqual(payload["status"]["button_action"], "restart")
        self.assertIsNotNone(queued_run)
        active_run.refresh_from_db()
        self.assertEqual(active_run.status, RoundQuestionAnalysisRun.STATUS_FAILED)
        self.assertIsNotNone(active_run.completed_at)
        self.assertIn("Restarted manually by Alex", active_run.error_message)
        queue_mock.assert_called_once_with(
            round_obj.id,
            trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
            initiated_by="Alex",
        )

    def test_round_analysis_question_returns_latest_completed_entry(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Lookup Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/lookup-round/edit#slide=id.r1",
        )
        old_run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=old_run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Old question text",
            answer_text="Old answer text",
            round_type="text",
            player_correctness={"Alex": ""},
        )
        latest_run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=latest_run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Latest question text",
            answer_text="Latest answer text",
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.get(
            reverse("round_analysis_question"),
            {"round_id": round_obj.id, "question_number": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["round_id"], round_obj.id)
        self.assertEqual(payload["analysis_run_id"], latest_run.id)
        self.assertEqual(payload["question_number"], 1)
        self.assertEqual(payload["question_text"], "Latest question text")
        self.assertEqual(payload["answer_text"], "Latest answer text")
        self.assertEqual(payload["possible_answers"], [])

    def test_build_possible_answers_expands_articles_and_synonyms(self):
        zebra_answers = _build_possible_answers("A Zebra")
        self.assertIn("A Zebra", zebra_answers)
        self.assertIn("a zebra", zebra_answers)
        self.assertIn("Zebra", zebra_answers)
        self.assertIn("zebra", zebra_answers)
        self.assertIn("Zebras", zebra_answers)
        self.assertIn("zebras", zebra_answers)

        crawl_answers = _build_possible_answers("Front crawl/freestyle.")
        self.assertIn("Front crawl/freestyle", crawl_answers)
        self.assertIn("front crawl/freestyle", crawl_answers)
        self.assertIn("Front crawl", crawl_answers)
        self.assertIn("front crawl", crawl_answers)
        self.assertIn("Front-crawl", crawl_answers)
        self.assertIn("front-crawl", crawl_answers)
        self.assertIn("Frontcrawl", crawl_answers)
        self.assertIn("frontcrawl", crawl_answers)
        self.assertIn("Freestyle", crawl_answers)
        self.assertIn("freestyle", crawl_answers)
        self.assertIn("Free style", crawl_answers)
        self.assertIn("free style", crawl_answers)
        self.assertIn("Front crawl or freestyle", crawl_answers)
        self.assertIn("front crawl or freestyle", crawl_answers)

        all_answers = _build_possible_answers("All of those")
        self.assertIn("All of those", all_answers)
        self.assertIn("all of those", all_answers)
        self.assertIn("All", all_answers)
        self.assertIn("all", all_answers)
        self.assertIn("All of the above", all_answers)
        self.assertIn("all of the above", all_answers)

    def test_build_possible_answers_with_aliases_expands_plausible_titles(self):
        empire_answers = _build_possible_answers_with_aliases(
            "Star Wars: The Empire Strikes Back",
            [
                "The Empire Strikes Back",
                "Empire Strikes Back",
                "ESB",
                "Star Wars Episode 5",
                "Star Wars Episode V",
            ],
        )
        self.assertIn("Star Wars: The Empire Strikes Back", empire_answers)
        self.assertIn("The Empire Strikes Back", empire_answers)
        self.assertIn("Empire Strikes Back", empire_answers)
        self.assertIn("ESB", empire_answers)
        self.assertIn("esb", empire_answers)
        self.assertIn("Star Wars Episode 5", empire_answers)
        self.assertIn("Star Wars Episode V", empire_answers)
        self.assertIn("Star Wars", empire_answers)
        self.assertIn("SW", empire_answers)
        self.assertIn("sw", empire_answers)

    def test_build_possible_answers_expands_punctuationless_titles_and_initialisms(self):
        kings_speech_answers = _build_possible_answers("King's Speech")
        self.assertIn("King's Speech", kings_speech_answers)
        self.assertIn("Kings Speech", kings_speech_answers)
        self.assertIn("kings speech", kings_speech_answers)
        self.assertIn("KS", kings_speech_answers)
        self.assertIn("ks", kings_speech_answers)

    def test_build_possible_answers_makes_parenthetical_text_optional(self):
        zebra_answers = _build_possible_answers("A Zebra (African)")
        self.assertIn("A Zebra (African)", zebra_answers)
        self.assertIn("A Zebra", zebra_answers)
        self.assertIn("a zebra", zebra_answers)
        self.assertIn("Zebra", zebra_answers)
        self.assertIn("zebra", zebra_answers)

    def test_build_possible_answers_expands_person_name_variants_with_question_context(self):
        franklin_answers = _build_possible_answers(
            "Benjamin Franklin",
            question_text="Which founding father appears on the $100 bill?",
        )
        self.assertIn("Benjamin Franklin", franklin_answers)
        self.assertIn("benjamin franklin", franklin_answers)
        self.assertIn("Franklin", franklin_answers)
        self.assertIn("franklin", franklin_answers)
        self.assertIn("Ben Franklin", franklin_answers)
        self.assertIn("ben franklin", franklin_answers)

    def test_build_possible_answers_expands_likely_person_name_variants_without_person_question_text(self):
        washington_answers = _build_possible_answers(
            "George Washington",
            question_text="Crossed the Delaware",
        )
        self.assertIn("George Washington", washington_answers)
        self.assertIn("Washington", washington_answers)
        self.assertIn("washington", washington_answers)
        self.assertIn("GW", washington_answers)
        self.assertIn("gw", washington_answers)

    def test_build_possible_answers_with_aliases_can_expand_person_aliases_from_surname(self):
        franklin_answers = _build_possible_answers_with_aliases(
            "Franklin",
            ["Benjamin Franklin"],
            question_text="Which founding father was known for electricity experiments?",
        )
        self.assertIn("Franklin", franklin_answers)
        self.assertIn("franklin", franklin_answers)
        self.assertIn("Benjamin Franklin", franklin_answers)
        self.assertIn("benjamin franklin", franklin_answers)
        self.assertIn("Ben Franklin", franklin_answers)
        self.assertIn("ben franklin", franklin_answers)

    @patch("GPTrivia.views._get_openai_client", return_value=object())
    @patch(
        "GPTrivia.views._create_openai_text_response",
        return_value='[{"question_number": 1, "aliases": ["Seven Years War", "Seven Years\' War"]}]',
    )
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-live-test"}, clear=False)
    def test_generate_additional_possible_answer_aliases_supports_semantic_alternate_names(
        self,
        response_mock,
        client_mock,
    ):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="History Round",
            major_category="History",
            minor_category1="Wars",
            minor_category2="Colonial",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        alias_map = _generate_additional_possible_answer_aliases(
            round_obj,
            [
                {
                    "question_number": 1,
                    "question_text": "What war was fought between Britain and France in North America from 1754 to 1763?",
                    "instruction_text": "",
                    "answer_text": "French and Indian War",
                },
            ],
            round_type="short answer",
        )

        self.assertEqual(
            alias_map,
            {1: ["Seven Years War", "Seven Years' War"]},
        )
        request_payload = response_mock.call_args.kwargs["input_items"][0]["content"][0]["text"]
        self.assertIn("instruction_text", request_payload)
        self.assertIn("French and Indian War", request_payload)

    def test_build_possible_answers_with_aliases_accepts_matching_round_short_forms(self):
        matching_answers = _build_possible_answers_with_aliases(
            "The British attempted to strengthen the Church of England's hold on the colonies with the establishment of the College of William and Mary in 1766, in order to reinforce British cultural and moral influence over colonial society.",
            ["church", "last", "C", "3", "third"],
            question_text="Match each statement to option A, B, or C.",
        )
        self.assertIn("church", matching_answers)
        self.assertIn("Church", matching_answers)
        self.assertIn("last", matching_answers)
        self.assertIn("Last", matching_answers)
        self.assertIn("C", matching_answers)
        self.assertIn("c", matching_answers)
        self.assertIn("3", matching_answers)
        self.assertIn("third", matching_answers)

    def test_build_possible_answers_with_aliases_accepts_matching_right_side_only(self):
        matching_answers = _build_possible_answers_with_aliases(
            "Alex - C. Defender",
            [],
            question_text="Alex",
        )
        self.assertIn("Defender", matching_answers)
        self.assertIn("defender", matching_answers)
        self.assertIn("C", matching_answers)
        self.assertIn("c", matching_answers)
        self.assertIn("3", matching_answers)
        self.assertIn("third", matching_answers)

    def test_normalize_analysis_questions_splits_matching_round_into_pairs(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 3,
                        "question_text": (
                            "1. Mercury\n"
                            "2. Venus\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "Match each planet to the correct description.",
                        "answer_text": "1-C\n2-B",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 2)
        self.assertEqual(normalized_payload["questions"][0]["question_number"], 1)
        self.assertEqual(normalized_payload["questions"][0]["question_text"], "Mercury")
        self.assertEqual(normalized_payload["questions"][0]["answer_text"], "third planet from the Sun")
        self.assertIn("C", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("3", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("third", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertEqual(normalized_payload["questions"][1]["question_number"], 2)
        self.assertEqual(normalized_payload["questions"][1]["question_text"], "Venus")
        self.assertEqual(normalized_payload["questions"][1]["answer_text"], "second planet from the Sun")
        self.assertIn("B", normalized_payload["questions"][1]["additional_possible_answers"])
        self.assertIn("2", normalized_payload["questions"][1]["additional_possible_answers"])

    def test_normalize_analysis_questions_ignores_overall_matching_question_number_when_splitting(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 3,
                        "question_text": (
                            "1. Match each planet to the correct description.\n"
                            "1. Mercury\n"
                            "2. Venus\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "",
                        "answer_text": "1-C\n2-B",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 2)
        self.assertEqual(normalized_payload["questions"][0]["question_text"], "Mercury")
        self.assertEqual(normalized_payload["questions"][1]["question_text"], "Venus")
        self.assertNotEqual(normalized_payload["questions"][0]["question_text"], "Match each planet to the correct description.")

    def test_normalize_analysis_questions_adds_position_aliases_for_pre_split_matching_entries(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 3,
                        "question_text": "Mercury",
                        "instruction_text": (
                            "Match Mercury to the correct description.\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "answer_text": "third planet from the Sun",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 1)
        self.assertEqual(normalized_payload["questions"][0]["answer_text"], "third planet from the Sun")
        self.assertIn("C", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("3", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("third", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("last", normalized_payload["questions"][0]["additional_possible_answers"])

    def test_normalize_analysis_questions_keeps_single_board_matching_question_when_slide_has_overall_number(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 11,
                        "source_slide_number": 3,
                        "question_text": (
                            "11\n"
                            "1. Mercury\n"
                            "2. Venus\n"
                            "3. Earth\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "Match each planet to the correct description.",
                        "answer_text": "1-C\n2-B\n3-A",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 1)
        self.assertEqual(normalized_payload["questions"][0]["answer_text"], "1-C\n2-B\n3-A")
        self.assertIn("CBA", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("321", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("last middle first", normalized_payload["questions"][0]["additional_possible_answers"])

    def test_normalize_analysis_questions_keeps_inline_numbered_matching_prompt_as_single_board(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 11,
                        "source_slide_number": 3,
                        "question_text": (
                            "11. Match each planet to the correct description.\n"
                            "1. Mercury\n"
                            "2. Venus\n"
                            "3. Earth\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "",
                        "answer_text": "CBA",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 1)
        self.assertEqual(normalized_payload["questions"][0]["answer_text"], "CBA")
        self.assertIn("CBA", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("321", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertIn("last middle first", normalized_payload["questions"][0]["additional_possible_answers"])

    def test_normalize_analysis_questions_splits_matching_round_from_compact_sequence_answer(self):
        normalized_payload = _normalize_analysis_questions(
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 3,
                        "question_text": (
                            "1. Mercury\n"
                            "2. Venus\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "Match each planet to the correct description.",
                        "answer_text": "CB",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            }
        )

        self.assertEqual(len(normalized_payload["questions"]), 2)
        self.assertEqual(normalized_payload["questions"][0]["question_text"], "Mercury")
        self.assertEqual(normalized_payload["questions"][0]["answer_text"], "third planet from the Sun")
        self.assertIn("C", normalized_payload["questions"][0]["additional_possible_answers"])
        self.assertEqual(normalized_payload["questions"][1]["question_text"], "Venus")
        self.assertEqual(normalized_payload["questions"][1]["answer_text"], "second planet from the Sun")
        self.assertIn("B", normalized_payload["questions"][1]["additional_possible_answers"])

    def test_round_analysis_question_can_include_saved_image_payload(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Image Lookup Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/image-lookup-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="Who is pictured here?",
            answer_text="Ada Lovelace",
            round_type="picture",
            media_kind="image",
            player_correctness={"Alex": ""},
        )
        image_buffer = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 120, 210)).save(image_buffer, format="PNG")
        entry.media_file.save("analysis-image.png", ContentFile(image_buffer.getvalue()), save=True)

        response = self.client.get(
            reverse("round_analysis_question"),
            {"round_id": round_obj.id, "question_number": 2, "include_image": "1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["media_kind"], "image")
        self.assertTrue(payload["image_url"].endswith(f"/round-analysis/entry/{entry.id}/image/"))
        self.assertEqual(payload["image_content_type"], "image/png")
        self.assertTrue(payload["image_data_url"].startswith("data:image/png;base64,"))

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={
            1: [
                "Zebra",
                "Striped zebra",
                "African zebra",
            ],
        },
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_saves_possible_answers(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Possible Answers Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/possible-answers-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "possible-answers-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "text",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": "What animal is white with black stripes?",
                        "instruction_text": "",
                        "answer_text": "A Zebra",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(entry.answer_text, "A Zebra")
        self.assertIn("A Zebra", entry.possible_answers)
        self.assertIn("a zebra", entry.possible_answers)
        self.assertIn("Zebra", entry.possible_answers)
        self.assertIn("zebras", entry.possible_answers)
        self.assertIn("Striped zebra", entry.possible_answers)
        self.assertIn("African zebra", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_multiple_choice_accepts_letters_and_numbers(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/multiple-choice-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "multiple-choice-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "multiple choice",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": (
                            "Which answer is correct?\n"
                            "A. Alpha wave\n"
                            "B. Beta decay\n"
                            "C. Gamma ray"
                        ),
                        "instruction_text": "",
                        "answer_text": "Gamma ray",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(entry.answer_text, "Gamma ray")
        self.assertIn("Gamma ray", entry.possible_answers)
        self.assertIn("C", entry.possible_answers)
        self.assertIn("c", entry.possible_answers)
        self.assertIn("3", entry.possible_answers)
        self.assertIn("third", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_multiple_choice_accepts_prefixed_answer_text(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Prefix Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/multiple-choice-prefix-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "multiple-choice-prefix-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "multiple choice",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": (
                            "Which answer is correct?\n"
                            "A. Alpha wave\n"
                            "B. Beta decay\n"
                            "C. Gamma ray"
                        ),
                        "instruction_text": "",
                        "answer_text": "C. Gamma ray",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertIn("C", entry.possible_answers)
        self.assertIn("c", entry.possible_answers)
        self.assertIn("3", entry.possible_answers)
        self.assertIn("third", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_multiple_choice_normalizes_hyphenated_round_type(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Hyphen Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/multiple-choice-hyphen-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "multiple-choice-hyphen-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "multiple-choice",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": (
                            "Which answer is correct?\n"
                            "A. Alpha wave\n"
                            "B. Beta decay\n"
                            "C. Gamma ray"
                        ),
                        "instruction_text": "",
                        "answer_text": "Gamma ray",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(entry.round_type, "multiple choice")
        self.assertIn("C", entry.possible_answers)
        self.assertIn("3", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_multiple_choice_uses_source_slide_options_when_question_text_omits_them(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Slide Fallback Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/multiple-choice-slide-fallback-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "multiple-choice-slide-fallback-presentation",
                "slide_range_label": "1-2",
                "slides": [
                    {
                        "slide_number": 1,
                        "slide_id": "slide-1",
                        "slide_url": "https://docs.google.com/presentation/d/fallback/edit#slide=id.slide-1",
                        "text": "",
                        "text_items": [
                            {"text": "Which answer is correct?", "position_x": 0, "position_y": 0, "width": 100, "height": 20},
                            {"text": "A. Alpha wave", "position_x": 0, "position_y": 40, "width": 100, "height": 20},
                            {"text": "B. Beta decay", "position_x": 0, "position_y": 60, "width": 100, "height": 20},
                            {"text": "C. Gamma ray", "position_x": 0, "position_y": 80, "width": 100, "height": 20},
                        ],
                        "media_items": [],
                        "line_items": [],
                        "speaker_notes": "",
                        "thumbnail_data_url": "",
                    },
                ],
            },
            {
                "round_type": "multiple choice",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": "Which answer is correct?",
                        "instruction_text": "",
                        "answer_text": "Gamma ray",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertIn("C", entry.possible_answers)
        self.assertIn("c", entry.possible_answers)
        self.assertIn("3", entry.possible_answers)
        self.assertIn("third", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_split_matching_question_accepts_position_aliases(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Split Matching Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/split-matching-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "split-matching-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 1,
                        "source_slide_number": 1,
                        "question_text": "Mercury",
                        "instruction_text": (
                            "Match Mercury to the correct description.\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "answer_text": "third planet from the Sun",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(entry.answer_text, "third planet from the Sun")
        self.assertIn("third planet from the Sun", entry.possible_answers)
        self.assertIn("C", entry.possible_answers)
        self.assertIn("c", entry.possible_answers)
        self.assertIn("3", entry.possible_answers)
        self.assertIn("third", entry.possible_answers)
        self.assertIn("last", entry.possible_answers)

    @patch(
        "GPTrivia.round_analysis._generate_additional_possible_answer_aliases",
        return_value={},
    )
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_single_board_matching_round_saves_sequence_aliases(self, correctness_mock, aliases_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Board Matching Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=11,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/board-matching-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        _store_round_analysis(
            run,
            {
                "presentation_id": "board-matching-presentation",
                "slide_range_label": "1-2",
                "slides": [],
            },
            {
                "round_type": "matching",
                "notes": "",
                "questions": [
                    {
                        "question_number": 11,
                        "source_slide_number": 1,
                        "question_text": (
                            "11\n"
                            "1. Mercury\n"
                            "2. Venus\n"
                            "3. Earth\n"
                            "A. first planet from the Sun\n"
                            "B. second planet from the Sun\n"
                            "C. third planet from the Sun"
                        ),
                        "instruction_text": "Match each planet to the correct description.",
                        "answer_text": "1-C\n2-B\n3-A",
                        "media_kind": "",
                        "major_category": "Science",
                        "minor_category1": "",
                        "minor_category2": "",
                    },
                ],
            },
        )

        entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(entry.answer_text, "1-C\n2-B\n3-A")
        self.assertIn("CBA", entry.possible_answers)
        self.assertIn("cba", entry.possible_answers)
        self.assertIn("321", entry.possible_answers)
        self.assertIn("last middle first", entry.possible_answers)

    def test_round_analysis_random_question_excludes_music_rounds(self):
        music_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Music Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=4,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/music-random-round/edit#slide=id.r1",
        )
        music_run = RoundQuestionAnalysisRun.objects.create(
            round=music_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=music_run,
            round=music_round,
            round_name=music_round.title,
            round_date=music_round.date,
            question_number=1,
            question_text="Name this song",
            answer_text="Song title",
            round_type="music",
            player_correctness={"Alex": ""},
        )

        valid_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Science Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=5,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/science-random-round/edit#slide=id.r1",
        )
        valid_run = RoundQuestionAnalysisRun.objects.create(
            round=valid_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=valid_run,
            round=valid_round,
            round_name=valid_round.title,
            round_date=valid_round.date,
            question_number=2,
            question_text="What particle has a negative charge?",
            answer_text="Electron",
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_random_question"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["round_id"], valid_round.id)
        self.assertEqual(payload["analysis_run_id"], valid_run.id)
        self.assertEqual(payload["question_number"], 2)
        self.assertEqual(payload["question_text"], "What particle has a negative charge?")
        self.assertEqual(payload["answer_text"], "Electron")

    def test_round_analysis_random_question_returns_404_when_only_music_rounds_exist(self):
        music_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Only Music Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=6,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/only-music-random-round/edit#slide=id.r1",
        )
        music_run = RoundQuestionAnalysisRun.objects.create(
            round=music_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=music_run,
            round=music_round,
            round_name=music_round.title,
            round_date=music_round.date,
            question_number=1,
            question_text="Name this song",
            answer_text="Song title",
            round_type="music",
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_random_question"))

        self.assertEqual(response.status_code, 404)

    def test_round_analysis_question_rejects_invalid_query_params(self):
        response = self.client.get(
            reverse("round_analysis_question"),
            {"round_id": "not-an-int", "question_number": "1"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "round_id must be an integer.")

    def test_normalize_analysis_categories_blanks_duplicate_major_and_minor_values(self):
        major, minor1, minor2 = _normalize_analysis_categories({
            "major_category": "Sports",
            "minor_category1": "Sports",
            "minor_category2": "Sports",
        })
        self.assertEqual((major, minor1, minor2), ("Sports", "", ""))

        major, minor1, minor2 = _normalize_analysis_categories({
            "major_category": "Sports",
            "minor_category1": "Team Names",
            "minor_category2": "Team Names",
        })
        self.assertEqual((major, minor1, minor2), ("Sports", "Team Names", ""))

    def test_optimize_analysis_image_content_caps_image_dimensions(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (2400, 1800), (120, 80, 220)).save(image_buffer, format="JPEG")
        optimized_content, optimized_extension = _optimize_analysis_image_content(image_buffer.getvalue())

        self.assertEqual(optimized_extension, ".jpg")
        self.assertTrue(optimized_content)

        with Image.open(io.BytesIO(optimized_content)) as optimized_image:
            self.assertLessEqual(max(optimized_image.size), 512)

    def test_extract_slide_media_items_marks_audio_placeholder_images(self):
        media_items = _extract_slide_media_items(
            {
                "pageElements": [
                    {
                        "objectId": "image-audio-control",
                        "title": "Audio clip",
                        "description": "Click to play song",
                        "size": {
                            "width": {"magnitude": 48, "unit": "PT"},
                            "height": {"magnitude": 48, "unit": "PT"},
                        },
                        "transform": {"translateX": 10, "translateY": 20},
                        "image": {
                            "contentUrl": "https://example.com/audio-placeholder.png",
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(media_items), 1)
        self.assertEqual(media_items[0]["kind"], "audio")
        self.assertTrue(media_items[0]["likely_audio_control"])

    def test_classify_round_structure_marks_multi_image_slide_as_picture_grid(self):
        round_obj = GPTriviaRound(
            title="Faces Round",
            creator="Alex",
            major_category="Entertainment",
            minor_category1="Movies",
            minor_category2="",
        )
        slide_payload = {
            "slides": [
                {
                    "slide_number": 1,
                    "text": "Identify these actors.",
                    "text_items": [],
                    "media_items": [
                        {"kind": "image", "media_index": 1},
                        {"kind": "image", "media_index": 2},
                    ],
                }
            ]
        }

        classification = _classify_round_structure(round_obj, slide_payload)

        self.assertEqual(classification["round_type"], "picture")
        self.assertEqual(classification["strategy"], "picture_grid_layout")

    def test_extract_picture_grid_questions_by_layout_matches_numbered_answers(self):
        round_obj = GPTriviaRound(
            title="Faces Round",
            creator="Alex",
            major_category="Entertainment",
            minor_category1="Movies",
            minor_category2="",
        )
        slide_payload = {
            "slides": [
                {
                    "slide_number": 1,
                    "text": "Identify the pictured actor.",
                    "text_items": [
                        {
                            "text": "1",
                            "position_x": 20,
                            "position_y": 20,
                            "width": 20,
                            "height": 20,
                        },
                        {
                            "text": "2",
                            "position_x": 220,
                            "position_y": 20,
                            "width": 20,
                            "height": 20,
                        },
                    ],
                    "media_items": [
                        {
                            "kind": "image",
                            "media_index": 1,
                            "url": "https://example.com/actor-1.png",
                            "download_url": "https://example.com/actor-1.png",
                            "position_x": 0,
                            "position_y": 0,
                            "width": 150,
                            "height": 150,
                        },
                        {
                            "kind": "image",
                            "media_index": 2,
                            "url": "https://example.com/actor-2.png",
                            "download_url": "https://example.com/actor-2.png",
                            "position_x": 200,
                            "position_y": 0,
                            "width": 150,
                            "height": 150,
                        },
                    ],
                },
                {
                    "slide_number": 2,
                    "text": "1. Actor One 2. Actor Two",
                    "text_items": [
                        {
                            "text": "1. Actor One",
                            "position_x": 0,
                            "position_y": 190,
                            "width": 150,
                            "height": 30,
                        },
                        {
                            "text": "2. Actor Two",
                            "position_x": 200,
                            "position_y": 190,
                            "width": 150,
                            "height": 30,
                        },
                    ],
                    "media_items": [],
                },
            ]
        }
        classification = {
            "round_type": "picture",
            "strategy": "picture_grid_layout",
            "notes": "Classified as a multi-image picture round from slide layout.",
        }

        analysis_payload = _extract_picture_grid_questions_by_layout(round_obj, slide_payload, classification)

        self.assertEqual(analysis_payload["round_type"], "picture")
        self.assertEqual(len(analysis_payload["questions"]), 2)
        self.assertEqual(analysis_payload["questions"][0]["answer_text"], "Actor One")
        self.assertEqual(analysis_payload["questions"][1]["answer_text"], "Actor Two")
        self.assertEqual(analysis_payload["questions"][0]["media_index"], 1)
        self.assertEqual(analysis_payload["questions"][1]["media_index"], 2)

    @patch("GPTrivia.round_analysis._analyze_round_slides_with_gpt")
    def test_analyze_round_slides_uses_layout_extractor_for_picture_grid(self, gpt_mock):
        round_obj = GPTriviaRound(
            title="Faces Round",
            creator="Alex",
            major_category="Entertainment",
            minor_category1="Movies",
            minor_category2="",
        )
        slide_payload = {
            "slides": [
                {
                    "slide_number": 1,
                    "text": "Identify the pictured actor.",
                    "text_items": [
                        {"text": "1", "position_x": 20, "position_y": 20, "width": 20, "height": 20},
                        {"text": "2", "position_x": 220, "position_y": 20, "width": 20, "height": 20},
                    ],
                    "media_items": [
                        {"kind": "image", "media_index": 1, "position_x": 0, "position_y": 0, "width": 150, "height": 150},
                        {"kind": "image", "media_index": 2, "position_x": 200, "position_y": 0, "width": 150, "height": 150},
                    ],
                },
                {
                    "slide_number": 2,
                    "text": "1. Actor One 2. Actor Two",
                    "text_items": [
                        {"text": "1. Actor One", "position_x": 0, "position_y": 190, "width": 150, "height": 30},
                        {"text": "2. Actor Two", "position_x": 200, "position_y": 190, "width": 150, "height": 30},
                    ],
                    "media_items": [],
                },
            ]
        }

        analysis_payload = _analyze_round_slides(round_obj, slide_payload)

        gpt_mock.assert_not_called()
        self.assertEqual(len(analysis_payload["questions"]), 2)

    def test_extract_slide_media_items_prefers_playable_link_for_audio_placeholder_images(self):
        media_items = _extract_slide_media_items(
            {
                "pageElements": [
                    {
                        "objectId": "image-audio-control",
                        "title": "Audio clip",
                        "description": "Click to play song",
                        "size": {
                            "width": {"magnitude": 48, "unit": "PT"},
                            "height": {"magnitude": 48, "unit": "PT"},
                        },
                        "transform": {"translateX": 10, "translateY": 20},
                        "image": {
                            "contentUrl": "https://example.com/audio-placeholder.png",
                        },
                        "imageProperties": {
                            "link": {
                                "url": "https://drive.google.com/file/d/audio123/view?usp=sharing",
                            }
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(media_items), 1)
        self.assertEqual(
            media_items[0]["url"],
            "https://drive.google.com/file/d/audio123/view?usp=sharing",
        )
        self.assertEqual(
            media_items[0]["playable_url"],
            "https://drive.google.com/file/d/audio123/view?usp=sharing",
        )
        self.assertEqual(media_items[0]["download_url"], "")
        self.assertEqual(
            media_items[0]["placeholder_url"],
            "https://example.com/audio-placeholder.png",
        )

    def test_extract_slide_line_items_includes_drawn_line_geometry(self):
        line_items = _extract_slide_line_items(
            {
                "pageElements": [
                    {
                        "objectId": "line-1",
                        "size": {
                            "width": {"magnitude": 180, "unit": "PT"},
                            "height": {"magnitude": 40, "unit": "PT"},
                        },
                        "transform": {
                            "translateX": 24,
                            "translateY": 120,
                        },
                        "line": {
                            "lineCategory": "STRAIGHT",
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(line_items), 1)
        self.assertEqual(line_items[0]["element_id"], "line-1")
        self.assertEqual(line_items[0]["line_category"], "STRAIGHT")
        self.assertEqual(line_items[0]["start_x"], 24.0)
        self.assertEqual(line_items[0]["start_y"], 120.0)
        self.assertEqual(line_items[0]["end_x"], 204.0)
        self.assertEqual(line_items[0]["end_y"], 160.0)

    def test_apply_apps_script_media_links_updates_audio_placeholder_to_external_url(self):
        enriched_items = _apply_apps_script_media_links(
            [
                {
                    "kind": "audio",
                    "element_id": "image-audio-control",
                    "url": "",
                    "playable_url": "",
                    "placeholder_url": "https://example.com/audio-placeholder.png",
                    "likely_audio_control": True,
                }
            ],
            {
                "image-audio-control": {
                    "linked_url": "https://drive.google.com/file/d/audio123/view?usp=sharing",
                    "linked_kind": "audio",
                }
            },
        )

        self.assertEqual(len(enriched_items), 1)
        self.assertEqual(enriched_items[0]["kind"], "audio")
        self.assertEqual(
            enriched_items[0]["playable_url"],
            "https://drive.google.com/file/d/audio123/view?usp=sharing",
        )
        self.assertEqual(
            enriched_items[0]["url"],
            "https://drive.google.com/file/d/audio123/view?usp=sharing",
        )

    def test_extract_embedded_slide_media_assets_prefers_audio_over_icon_images(self):
        pptx_buffer = io.BytesIO()
        with zipfile.ZipFile(pptx_buffer, "w") as archive:
            archive.writestr(
                "ppt/slides/_rels/slide1.xml.rels",
                """<?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/icon.png"/>
                    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio" Target="../media/clip.mp3"/>
                </Relationships>""",
            )
            archive.writestr("ppt/media/icon.png", b"png")
            archive.writestr("ppt/media/clip.mp3", b"mp3")

        assets = _extract_embedded_slide_media_assets(pptx_buffer.getvalue(), 1)

        self.assertEqual([asset["kind"] for asset in assets[:2]], ["audio", "image"])
        self.assertEqual(assets[0]["filename"], "clip.mp3")
        self.assertEqual(assets[0]["content"], b"mp3")

    def test_placeholder_media_url_flags_image_when_audio_expected(self):
        self.assertTrue(_is_placeholder_media_url("https://example.com/audio-placeholder.png", expected_kind="audio"))
        self.assertFalse(_is_placeholder_media_url("https://example.com/track.mp3", expected_kind="audio"))

    @patch("GPTrivia.round_analysis._collect_category_options", return_value=(["Music"], ["Songs"]))
    @patch("GPTrivia.views._get_openai_client", return_value=object())
    @patch("GPTrivia.views._create_openai_text_response", return_value='{"round_type":"music","notes":"","questions":[]}')
    def test_analyze_round_slides_includes_slide_thumbnails_and_notes(self, response_mock, _client_mock, _category_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Audio Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/audio-round/edit#slide=id.r1",
        )
        slide_payload = {
            "presentation_id": "audio-round",
            "slide_range_label": "1-1",
            "slides": [
                {
                    "slide_number": 1,
                    "slide_id": "slide-1",
                    "slide_url": "https://docs.google.com/presentation/d/audio-round/edit#slide=id.slide-1",
                    "text": "",
                    "speaker_notes": "Reveal all lyrics here.",
                    "media_items": [
                        {
                            "kind": "audio",
                            "media_index": 1,
                            "title": "Audio clip",
                            "description": "Click to play song",
                            "likely_audio_control": True,
                        }
                    ],
                    "thumbnail_data_url": "data:image/png;base64,abc123",
                }
            ],
        }

        _analyze_round_slides(round_obj, slide_payload)

        input_items = response_mock.call_args.kwargs["input_items"]
        content_items = input_items[0]["content"]
        self.assertEqual(content_items[1]["type"], "input_image")
        self.assertEqual(content_items[1]["image_url"], "data:image/png;base64,abc123")
        serialized_payload = content_items[0]["text"]
        self.assertIn('"speaker_notes": "Reveal all lyrics here."', serialized_payload)
        self.assertIn('"likely_audio_control": true', serialized_payload)

    @patch("GPTrivia.round_analysis.time.sleep")
    @patch("GPTrivia.round_analysis.requests.get")
    def test_fetch_url_with_retries_returns_none_after_repeated_failures(self, get_mock, _sleep_mock):
        get_mock.side_effect = requests.HTTPError("500 Server Error")

        response = _fetch_url_with_retries(
            "https://lh7-us.googleusercontent.com/example=s1600",
            log_context="test asset",
        )

        self.assertIsNone(response)
        self.assertEqual(get_mock.call_count, 3)

    @patch("GPTrivia.round_analysis.time.sleep")
    @patch("GPTrivia.round_analysis.requests.get")
    def test_fetch_slide_thumbnail_data_url_skips_after_retries_fail(self, get_mock, _sleep_mock):
        slides_service = (
            type("SlidesService", (), {
                "presentations": lambda self: type("Presentations", (), {
                    "pages": lambda self: type("Pages", (), {
                        "getThumbnail": lambda self, **kwargs: type("ThumbnailRequest", (), {
                            "execute": lambda self: {"contentUrl": "https://lh7-us.googleusercontent.com/example=s1600"}
                        })()
                    })()
                })()
            })()
        )
        get_mock.side_effect = requests.HTTPError("500 Server Error")

        data_url = _fetch_slide_thumbnail_data_url(
            slides_service,
            credentials=None,
            presentation_id="presentation-1",
            slide_id="slide-1",
        )

        self.assertEqual(data_url, "")
        self.assertEqual(get_mock.call_count, 3)

    @patch("GPTrivia.round_analysis._download_media_file", return_value=None)
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_assigns_distinct_media_from_same_slide(self, _correctness_mock, _download_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Picture Grid Round",
            major_category="Entertainment",
            minor_category1="Movies",
            minor_category2="Images",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/picture-grid/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        slide_payload = {
            "presentation_id": "picture-grid",
            "slide_range_label": "1-2",
            "slides": [
                {
                    "slide_number": 1,
                    "slide_id": "slide-question",
                    "slide_url": "https://docs.google.com/presentation/d/picture-grid/edit#slide=id.slide-question",
                    "text": "Identify these ten actors.",
                    "media_items": [
                        {
                            "kind": "image",
                            "media_index": 1,
                            "url": "https://example.com/actor-1.png",
                            "download_url": "https://example.com/actor-1.png",
                        },
                        {
                            "kind": "image",
                            "media_index": 2,
                            "url": "https://example.com/actor-2.png",
                            "download_url": "https://example.com/actor-2.png",
                        },
                    ],
                }
            ],
        }
        analysis_payload = {
            "round_type": "picture",
            "notes": "Identify the pictured actor.",
            "questions": [
                {
                    "question_number": 1,
                    "source_slide_number": 1,
                    "question_text": "Actor 1",
                    "instruction_text": "Identify the pictured actor.",
                    "answer_text": "Actor One",
                    "media_kind": "image",
                    "major_category": "Entertainment",
                    "minor_category1": "Movies",
                    "minor_category2": "",
                },
                {
                    "question_number": 2,
                    "source_slide_number": 1,
                    "question_text": "Actor 2",
                    "instruction_text": "Identify the pictured actor.",
                    "answer_text": "Actor Two",
                    "media_kind": "image",
                    "major_category": "Entertainment",
                    "minor_category1": "Movies",
                    "minor_category2": "",
                },
            ],
        }

        _store_round_analysis(run, slide_payload, analysis_payload)

        saved_entries = list(RoundQuestionAnalysisEntry.objects.filter(run=run).order_by("question_number"))
        self.assertEqual(len(saved_entries), 2)
        self.assertEqual(saved_entries[0].media_url, "https://example.com/actor-1.png")
        self.assertEqual(saved_entries[1].media_url, "https://example.com/actor-2.png")

    @patch("GPTrivia.round_analysis._download_media_file", return_value=None)
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_does_not_borrow_media_from_other_slides(self, _correctness_mock, _download_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Mixed Media Round",
            major_category="Entertainment",
            minor_category1="Movies",
            minor_category2="Images",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/mixed-media/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        slide_payload = {
            "presentation_id": "mixed-media",
            "slide_range_label": "1-2",
            "slides": [
                {
                    "slide_number": 1,
                    "slide_id": "slide-1",
                    "slide_url": "https://docs.google.com/presentation/d/mixed-media/edit#slide=id.slide-1",
                    "text": "Question text only.",
                    "media_items": [],
                },
                {
                    "slide_number": 2,
                    "slide_id": "slide-2",
                    "slide_url": "https://docs.google.com/presentation/d/mixed-media/edit#slide=id.slide-2",
                    "text": "Image on a different slide.",
                    "media_items": [
                        {
                            "kind": "image",
                            "media_index": 1,
                            "url": "https://example.com/actor-1.png",
                            "download_url": "https://example.com/actor-1.png",
                        },
                    ],
                },
            ],
        }
        analysis_payload = {
            "round_type": "picture",
            "notes": "",
            "questions": [
                {
                    "question_number": 1,
                    "source_slide_number": 1,
                    "question_text": "Question without image on its own slide",
                    "instruction_text": "Identify the pictured actor.",
                    "answer_text": "Actor One",
                    "media_kind": "image",
                    "major_category": "Entertainment",
                    "minor_category1": "Movies",
                    "minor_category2": "",
                },
            ],
        }

        _store_round_analysis(run, slide_payload, analysis_payload)

        saved_entry = RoundQuestionAnalysisEntry.objects.get(run=run, question_number=1)
        self.assertEqual(saved_entry.media_kind, "image")
        self.assertEqual(saved_entry.media_url, "")
        self.assertFalse(saved_entry.media_file)

    @patch("GPTrivia.round_analysis._download_media_file", return_value=None)
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_uses_playable_url_for_audio_placeholders(self, _correctness_mock, _download_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Music Identify Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/music-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )

        slide_payload = {
            "presentation_id": "music-round",
            "slide_range_label": "1-1",
            "slides": [
                {
                    "slide_number": 1,
                    "slide_id": "slide-question",
                    "slide_url": "https://docs.google.com/presentation/d/music-round/edit#slide=id.slide-question",
                    "text": "Name the song and artist.",
                    "media_items": [
                        {
                            "kind": "audio",
                            "media_index": 1,
                            "url": "https://drive.google.com/file/d/audio123/view?usp=sharing",
                            "playable_url": "https://drive.google.com/file/d/audio123/view?usp=sharing",
                            "download_url": "",
                            "placeholder_url": "https://example.com/audio-placeholder.png",
                            "likely_audio_control": True,
                        }
                    ],
                }
            ],
        }
        analysis_payload = {
            "round_type": "music",
            "notes": "Identify the song and artist from the clip.",
            "questions": [
                {
                    "question_number": 1,
                    "source_slide_number": 1,
                    "question_text": "Clip 1",
                    "instruction_text": "Name the song and artist.",
                    "answer_text": "Song One - Artist One",
                    "media_kind": "image",
                    "major_category": "Music",
                    "minor_category1": "Songs",
                    "minor_category2": "",
                }
            ],
        }

        _store_round_analysis(run, slide_payload, analysis_payload)

        saved_entry = RoundQuestionAnalysisEntry.objects.get(run=run)
        self.assertEqual(saved_entry.media_kind, "audio")
        self.assertEqual(
            saved_entry.media_url,
            "https://drive.google.com/file/d/audio123/view?usp=sharing",
        )
        self.assertFalse(saved_entry.media_file)

    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=True)
    @patch("GPTrivia.round_analysis.get_round_analysis_playable_media_url", return_value="")
    @patch(
        "GPTrivia.round_analysis.get_round_analysis_playable_media_asset",
        return_value={
            "filename": "clip.mp3",
            "content_type": "audio/mpeg",
            "content": b"mp3-bytes",
            "kind": "audio",
        },
    )
    def test_round_analysis_media_streams_embedded_audio_when_placeholder_only(self, _asset_mock, _rebuilt_url_mock, _placeholder_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Embedded Audio Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/embedded-audio-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="embedded-audio-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://example.com/audio-placeholder.png",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertIn('filename="clip.mp3"', response["Content-Disposition"])

    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=False)
    def test_round_analysis_media_redirects_to_external_playable_url(self, _placeholder_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="External Audio Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/external-audio-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="external-audio-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://drive.google.com/file/d/audio123/view?usp=sharing",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://drive.google.com/file/d/audio123/view?usp=sharing")

    @patch(
        "GPTrivia.round_analysis.get_round_analysis_playable_media_url",
        return_value="https://drive.google.com/file/d/audio456/view?usp=sharing",
    )
    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=True)
    def test_round_analysis_media_redirects_to_rebuilt_slide_link(self, _placeholder_mock, _rebuilt_url_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Rebuilt Audio Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/rebuilt-audio-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="rebuilt-audio-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://example.com/audio-placeholder.png",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://drive.google.com/file/d/audio456/view?usp=sharing")

    @patch(
        "GPTrivia.round_analysis.get_round_analysis_playable_media_url",
        return_value="https://drive.google.com/file/d/audio789/view?usp=sharing",
    )
    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=False)
    def test_round_analysis_media_prefers_rebuilt_slide_link_over_saved_image_url(self, _placeholder_mock, _rebuilt_url_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Custom Placeholder Image Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/custom-image-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="custom-image-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://cdn.example.com/custom-audio-button",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://drive.google.com/file/d/audio789/view?usp=sharing")

    @patch("GPTrivia.round_analysis.get_round_analysis_playable_media_url", return_value="")
    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=True)
    @patch("GPTrivia.round_analysis.get_round_analysis_playable_media_asset", side_effect=RuntimeError("bad export"))
    def test_round_analysis_media_returns_404_when_fallback_resolution_fails(self, _asset_mock, _placeholder_mock, _rebuilt_url_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Broken Audio Round",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/broken-audio-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="broken-audio-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://example.com/audio-placeholder.png",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 404)

    @patch("GPTrivia.round_analysis._is_placeholder_media_url", return_value=True)
    @patch("GPTrivia.round_analysis.get_round_analysis_playable_media_url", return_value="")
    @patch(
        "GPTrivia.round_analysis.get_round_analysis_playable_media_asset",
        return_value={
            "filename": "clip.mp3",
            "content_type": "audio/mpeg",
            "content": b"mp3-bytes",
            "kind": "audio",
        },
    )
    def test_round_analysis_media_ignores_saved_image_for_audio_entry(self, _asset_mock, _rebuilt_url_mock, _placeholder_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Audio Entry With Old Icon",
            major_category="Music",
            minor_category1="Songs",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/audio-icon-round/edit#slide=id.r1",
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="music",
            source_presentation_id="audio-icon-round",
            source_slide_range="1-1",
        )
        entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Clip 1",
            answer_text="Song",
            round_type="music",
            media_kind="audio",
            media_url="https://example.com/audio-placeholder.png",
            source_slide_number=1,
            player_correctness={"Alex": ""},
        )
        entry.media_file.save("old-icon.png", ContentFile(b"png-bytes"), save=True)

        response = self.client.get(reverse("round_analysis_media", args=[entry.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertIn('filename="clip.mp3"', response["Content-Disposition"])

    @patch("GPTrivia.round_analysis._download_media_file", return_value=None)
    @patch("GPTrivia.round_analysis._empty_player_correctness_map", return_value={"Alex": ""})
    def test_store_round_analysis_replaces_older_runs_for_round(self, _correctness_mock, _download_mock):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Replace Older Run",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/replace-older-run/edit#slide=id.r1",
        )
        old_run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=old_run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Old question",
            answer_text="Old answer",
            round_type="picture",
            player_correctness={"Alex": ""},
        )
        new_run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
        )
        slide_payload = {
            "presentation_id": "replace-older-run",
            "slide_range_label": "1-1",
            "slides": [
                {
                    "slide_number": 1,
                    "slide_id": "slide-question",
                    "slide_url": "https://docs.google.com/presentation/d/replace-older-run/edit#slide=id.slide-question",
                    "text": "New question",
                    "media_items": [],
                }
            ],
        }
        analysis_payload = {
            "round_type": "short answer",
            "notes": "Updated analysis",
            "questions": [
                {
                    "question_number": 1,
                    "source_slide_number": 1,
                    "question_text": "New question",
                    "instruction_text": "",
                    "answer_text": "New answer",
                    "media_kind": "",
                    "major_category": "Science",
                    "minor_category1": "Physics",
                    "minor_category2": "",
                }
            ],
        }

        _store_round_analysis(new_run, slide_payload, analysis_payload)

        self.assertEqual(RoundQuestionAnalysisRun.objects.filter(round=round_obj).count(), 1)
        self.assertFalse(RoundQuestionAnalysisRun.objects.filter(id=old_run.id).exists())
        self.assertTrue(RoundQuestionAnalysisRun.objects.filter(id=new_run.id).exists())
        saved_entries = list(RoundQuestionAnalysisEntry.objects.filter(run=new_run))
        self.assertEqual(len(saved_entries), 1)
        self.assertEqual(saved_entries[0].question_text, "New question")

    def test_rounds_list_keeps_analyze_button_enabled_for_existing_analysis(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Disable Button Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/disable-button/edit#slide=id.r1",
        )
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )

        response = self.client.get(reverse("rounds_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analyze Again")
        self.assertContains(response, "Already analyzed")
        self.assertNotContains(response, 'disabled aria-disabled="true"', html=False)
        self.assertContains(response, f'data-status-url="/round-analysis/{round_obj.id}/status/"', html=False)

    def test_rounds_list_hides_analyze_button_for_creator_without_opt_in(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Opt In Required",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 20),
            round_number=4,
            max_score=10,
            replay=False,
            cooperative=False,
            link="https://docs.google.com/presentation/d/opt-in-required/edit#slide=id.r1",
        )

        response = self.client.get(reverse("rounds_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'action="{reverse("trigger_round_analysis", args=[round_obj.id])}" class="round-analysis-form"',
            html=False,
        )
