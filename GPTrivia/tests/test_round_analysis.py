import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import GPTriviaRound, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun


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
            answer_text="Crab Nebula",
            round_type="picture",
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
        self.assertContains(response, "Crab Nebula")
