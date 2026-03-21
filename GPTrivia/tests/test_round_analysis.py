import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import GPTriviaRound, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun
from GPTrivia.round_analysis import _normalize_analysis_categories, _store_round_analysis


class RoundAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="Alex", password="pw")
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
    @patch("GPTrivia.round_analysis.queue_round_analysis_batch")
    def test_home_generate_auto_queues_only_new_rounds(self, queue_mock, create_mock):
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
        self.assertEqual(create_mock.call_count, 1)
        created_rounds = list(GPTriviaRound.objects.order_by("round_number", "id"))
        self.assertEqual([round_obj.title for round_obj in created_rounds], ["Fresh Round", "Historic Round"])
        queue_mock.assert_called_once()
        queued_ids = queue_mock.call_args.args[0]
        self.assertEqual(queued_ids, [created_rounds[0].id])
        self.assertEqual(queue_mock.call_args.kwargs["trigger_type"], RoundQuestionAnalysisRun.TRIGGER_AUTO)
        self.assertEqual(queue_mock.call_args.kwargs["initiated_by"], "Alex")

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
