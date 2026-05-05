import json
import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import (
    AnswerSheetEntry,
    GPTriviaRound,
    MergedPresentation,
    Profile,
    RoundQuestionAnalysisEntry,
    RoundQuestionAnalysisRun,
)
from GPTrivia.player_scores import get_round_score_map


class AnswerSheetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="Alex", password="pw")
        self.client.force_login(self.user)

    def test_answer_sheet_defaults_to_latest_round_date_and_prefills_answers(self):
        older_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Older Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 10),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        latest_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Latest Round",
            major_category="Science",
            minor_category1="Biology",
            minor_category2="Life",
            date=datetime.date(2026, 4, 17),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=latest_round,
            trivia_date=latest_round.date,
            answers=["Alpha", "Beta"] + [""] * 8,
        )

        response = self.client.get(reverse("answer_sheet"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_date"], "2026-04-17")
        round_pages = response.context["round_pages"]
        self.assertEqual([page["round_id"] for page in round_pages], [latest_round.id])
        self.assertEqual(round_pages[0]["answers"][0:2], ["Alpha", "Beta"])
        self.assertEqual(round_pages[0]["score_value"], "")
        self.assertContains(response, "Latest Round")
        self.assertContains(response, "Alpha\nBeta", html=False)
        self.assertNotContains(response, "Older Round")
        self.assertTrue(older_round.id)

    def test_answer_sheet_respects_requested_date(self):
        older_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Older Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 10),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Latest Round",
            major_category="Science",
            minor_category1="Biology",
            minor_category2="Life",
            date=datetime.date(2026, 4, 17),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        response = self.client.get(reverse("answer_sheet"), {"date": "2026-04-10"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_date"], "2026-04-10")
        self.assertEqual([page["round_id"] for page in response.context["round_pages"]], [older_round.id])

    def test_save_answer_sheet_entry_creates_and_updates_answers(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Save Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        create_response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "One\nTwo\nThree",
            }),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertEqual(entry.trivia_date, round_obj.date)
        self.assertEqual(entry.answers[:4], ["One", "Two", "Three", ""])
        self.assertEqual(len(entry.answers), 10)

        update_response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": ["Updated", "Answer"],
            }),
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(AnswerSheetEntry.objects.filter(user=self.user, round=round_obj).count(), 1)
        self.assertEqual(entry.answers[:3], ["Updated", "Answer", ""])

    def test_save_answer_sheet_entry_preserves_rows_beyond_ten(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Long Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        create_response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": [f"Answer {index}" for index in range(1, 13)],
            }),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertEqual(len(entry.answers), 12)
        self.assertEqual(entry.answers[9], "Answer 10")
        self.assertEqual(entry.answers[10], "Answer 11")
        self.assertEqual(entry.answers[11], "Answer 12")

        response = self.client.get(reverse("answer_sheet"))
        self.assertEqual(response.status_code, 200)
        round_pages = response.context["round_pages"]
        self.assertEqual(len(round_pages[0]["answers"]), 12)
        self.assertIn("Answer 11\nAnswer 12", round_pages[0]["answers_text"])

    def test_save_answer_sheet_entry_persists_pencil_mode_and_ink_strokes(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Pencil Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "One\nTwo",
                "input_mode": "pencil",
                "ink_strokes": [
                    [{"x": 0.1, "y": 0.2}, {"x": 0.4, "y": 0.5, "p": 0.8}],
                    [{"x": 0.7, "y": 0.8}],
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertEqual(entry.input_mode, AnswerSheetEntry.INPUT_MODE_PENCIL)
        self.assertEqual(entry.ink_strokes[0][0], {"x": 0.1, "y": 0.2})
        self.assertEqual(entry.ink_strokes[0][1], {"x": 0.4, "y": 0.5, "p": 0.8})
        self.assertEqual(response.json()["input_mode"], "pencil")
        self.assertEqual(response.json()["ink_strokes"][1][0], {"x": 0.7, "y": 0.8})

    def test_save_answer_sheet_entry_clears_grade_overrides_for_changed_rows(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Override Clear Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        entry = AnswerSheetEntry.objects.create(
            user=self.user,
            round=round_obj,
            trivia_date=round_obj.date,
            answers=["Old 1", "Old 2"] + [""] * 8,
            grade_overrides=[1, 2],
        )

        response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": ["New 1", "Old 2"] + [""] * 8,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.answers[:2], ["New 1", "Old 2"])
        self.assertEqual(entry.grade_overrides, [2])

    def test_save_answer_sheet_entry_shares_cooperative_answers_across_players_for_night(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        jenny = User.objects.create_user(username="Jenny", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Co-op Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_jenny": "score_jenny",
            },
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.post(
                    reverse("save_answer_sheet_entry"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "answers": "One\nTwo\nThree",
                        "client_id": "coop-client-1",
                    }),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(AnswerSheetEntry.objects.filter(round=round_obj).count(), 3)
            self.assertEqual(
                AnswerSheetEntry.objects.get(user=self.user, round=round_obj).answers[:4],
                ["One", "Two", "Three", ""],
            )
            self.assertEqual(
                AnswerSheetEntry.objects.get(user=megan, round=round_obj).answers[:4],
                ["One", "Two", "Three", ""],
            )
            self.assertEqual(
                AnswerSheetEntry.objects.get(user=jenny, round=round_obj).answers[:4],
                ["One", "Two", "Three", ""],
            )
            self.assertTrue(response.json()["shared"])
            self.assertEqual(len(callbacks), 1)
            broadcast.assert_not_called()

            callbacks[0]()
            broadcast.assert_called_once()
            message = broadcast.call_args.args[0]
            self.assertEqual(message["action"], "answer_sheet")
            self.assertEqual(message["event"], "answer_sheet_save")
            self.assertEqual(message["client_id"], "coop-client-1")
            self.assertEqual(message["round_id"], round_obj.id)
            self.assertEqual(message["answers"][:4], ["One", "Two", "Three", ""])
            self.assertEqual(message["input_mode"], "text")
            self.assertEqual(message["ink_strokes"], [])

        other_client = self.client_class()
        other_client.force_login(jenny)
        shared_response = other_client.get(reverse("answer_sheet"), {"date": trivia_date.isoformat()})
        self.assertEqual(shared_response.status_code, 200)
        round_pages = shared_response.context["round_pages"]
        self.assertEqual(round_pages[0]["answers"][:4], ["One", "Two", "Three", ""])
        self.assertEqual(round_pages[0]["input_mode"], "text")
        self.assertEqual(round_pages[0]["ink_strokes"], [])

    def test_save_answer_sheet_entry_shares_pencil_mode_and_ink_strokes_across_coop_round(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Pencil Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )

        response = self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": ["One"] + [""] * 9,
                "input_mode": "pencil",
                "ink_strokes": [[{"x": 0.25, "y": 0.3}, {"x": 0.55, "y": 0.65}]],
                "client_id": "coop-pencil-1",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=megan, round=round_obj).input_mode,
            AnswerSheetEntry.INPUT_MODE_PENCIL,
        )
        shared_response = self.client.get(reverse("answer_sheet_sync"), {"date": trivia_date.isoformat()})
        self.assertEqual(shared_response.status_code, 200)
        round_payload = shared_response.json()["rounds"][0]
        self.assertEqual(round_payload["input_mode"], "pencil")
        self.assertEqual(round_payload["ink_strokes"], [[{"x": 0.25, "y": 0.3}, {"x": 0.55, "y": 0.65}]])

    def test_save_answer_sheet_entry_invalidates_only_changed_rows_for_shared_graded_round(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Invalidated Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="What is the fastest land animal?",
            answer_text="Cheetah",
            possible_answers=["Cheetah", "cheetah"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=round_obj,
            trivia_date=trivia_date,
            answers=["Zebra", "Cheetah"] + [""] * 8,
            grade_invalidated_questions=[],
            was_graded=True,
            is_diverged=False,
        )
        AnswerSheetEntry.objects.create(
            user=megan,
            round=round_obj,
            trivia_date=trivia_date,
            answers=["Zebra", "Cheetah"] + [""] * 8,
            grade_invalidated_questions=[],
            was_graded=True,
            is_diverged=False,
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.post(
                    reverse("save_answer_sheet_entry"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "answers": ["Zebra", "Lion"] + [""] * 8,
                        "client_id": "invalidate-client-1",
                    }),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["shared"])
            self.assertTrue(payload["was_graded"])
            self.assertEqual(payload["grade_invalidated_questions"], [2])
            self.assertEqual(payload["grade_payload"]["score"], 1)
            self.assertEqual(payload["grade_payload"]["row_results"][0]["state"], "correct")
            self.assertEqual(payload["grade_payload"]["row_results"][1]["state"], "default")
            self.assertTrue(payload["grade_payload"]["row_results"][1]["invalidated"])
            self.assertEqual(len(callbacks), 1)
            broadcast.assert_not_called()

            alex_entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
            megan_entry = AnswerSheetEntry.objects.get(user=megan, round=round_obj)
            self.assertEqual(alex_entry.grade_invalidated_questions, [2])
            self.assertEqual(megan_entry.grade_invalidated_questions, [2])
            self.assertTrue(alex_entry.was_graded)
            self.assertTrue(megan_entry.was_graded)

            callbacks[0]()
            broadcast.assert_called_once()
            message = broadcast.call_args.args[0]
            self.assertEqual(message["event"], "answer_sheet_save")
            self.assertEqual(message["client_id"], "invalidate-client-1")
            self.assertEqual(message["grade_payload"]["score"], 1)
            self.assertEqual(message["grade_payload"]["row_results"][0]["state"], "correct")
            self.assertEqual(message["grade_payload"]["row_results"][1]["state"], "default")

    def test_answer_sheet_sync_returns_current_communal_round_state(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        cooperative_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Sync Co-op Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
            score_alex=6.5,
        )
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Solo Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=cooperative_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=cooperative_round,
            round_name=cooperative_round.title,
            round_date=cooperative_round.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        AnswerSheetEntry.objects.create(
            user=megan,
            round=cooperative_round,
            trivia_date=trivia_date,
            answers=["Zebra"] + [""] * 9,
            grade_overrides=[1],
            grade_rejections=[],
            is_diverged=False,
        )

        response = self.client.get(
            reverse("answer_sheet_sync"),
            {"date": trivia_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_date"], trivia_date.isoformat())
        self.assertEqual(len(payload["rounds"]), 1)
        round_payload = payload["rounds"][0]
        self.assertEqual(round_payload["round_id"], cooperative_round.id)
        self.assertEqual(round_payload["answers"][0], "Zebra")
        self.assertEqual(round_payload["input_mode"], "text")
        self.assertEqual(round_payload["ink_strokes"], [])
        self.assertEqual(round_payload["score_value"], "6.5")
        self.assertTrue(round_payload["shared"])
        self.assertFalse(round_payload["is_diverged"])
        self.assertEqual(round_payload["grade_payload"]["score"], 1)
        self.assertEqual(round_payload["grade_payload"]["row_results"][0]["state"], "correct")

    def test_answer_sheet_sync_restores_saved_grade_state_without_manual_overrides(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        cooperative_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Restored Grade State Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
            score_alex=4,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=cooperative_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=cooperative_round,
            round_name=cooperative_round.title,
            round_date=cooperative_round.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=cooperative_round,
            round_name=cooperative_round.title,
            round_date=cooperative_round.date,
            question_number=2,
            question_text="What is the fastest land animal?",
            answer_text="Cheetah",
            possible_answers=["Cheetah", "cheetah"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        AnswerSheetEntry.objects.create(
            user=megan,
            round=cooperative_round,
            trivia_date=trivia_date,
            answers=["Zebra", "Cheetah"] + [""] * 8,
            grade_overrides=[],
            grade_rejections=[],
            grade_invalidated_questions=[2],
            was_graded=True,
            is_diverged=False,
        )

        response = self.client.get(
            reverse("answer_sheet_sync"),
            {"date": trivia_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["answers"][:2], ["Zebra", "Cheetah"])
        self.assertEqual(round_payload["grade_payload"]["score"], 1)
        self.assertEqual(round_payload["grade_payload"]["row_results"][0]["state"], "correct")
        self.assertEqual(round_payload["grade_payload"]["row_results"][1]["state"], "default")
        self.assertTrue(round_payload["grade_payload"]["row_results"][1]["invalidated"])

    def test_diverge_answer_sheet_round_stops_future_shared_answer_updates(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        jenny = User.objects.create_user(username="Jenny", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Diverge Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_jenny": "score_jenny",
            },
        )

        self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Shared\nAnswers",
                "client_id": "shared-client",
            }),
            content_type="application/json",
        )

        diverge_response = self.client.post(
            reverse("diverge_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Mine\nOnly",
            }),
            content_type="application/json",
        )

        self.assertEqual(diverge_response.status_code, 200)
        self.assertTrue(AnswerSheetEntry.objects.get(user=self.user, round=round_obj).is_diverged)

        other_client = self.client_class()
        other_client.force_login(megan)
        with patch("GPTrivia.views._broadcast_scoresheet_message"):
            other_client.post(
                reverse("save_answer_sheet_entry"),
                data=json.dumps({
                    "round_id": round_obj.id,
                    "answers": "Updated\nShared",
                    "client_id": "shared-client-2",
                }),
                content_type="application/json",
            )

        self.assertEqual(
            AnswerSheetEntry.objects.get(user=self.user, round=round_obj).answers[:3],
            ["Mine", "Only", ""],
        )
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=megan, round=round_obj).answers[:3],
            ["Updated", "Shared", ""],
        )
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=jenny, round=round_obj).answers[:3],
            ["Updated", "Shared", ""],
        )

    def test_merge_answer_sheet_round_restores_communal_answers_and_future_sync(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        jenny = User.objects.create_user(username="Jenny", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Merge Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_jenny": "score_jenny",
            },
        )

        self.client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Shared\nAnswers",
                "client_id": "shared-client",
            }),
            content_type="application/json",
        )

        self.client.post(
            reverse("diverge_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Mine\nOnly",
            }),
            content_type="application/json",
        )

        other_client = self.client_class()
        other_client.force_login(megan)
        other_client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Updated\nShared",
                "client_id": "shared-client-2",
            }),
            content_type="application/json",
        )

        merge_response = self.client.post(
            reverse("merge_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(merge_response.status_code, 200)
        merged_entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertFalse(merged_entry.is_diverged)
        self.assertEqual(merged_entry.answers[:3], ["Updated", "Shared", ""])

        final_client = self.client_class()
        final_client.force_login(jenny)
        final_client.post(
            reverse("save_answer_sheet_entry"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Final\nShared",
                "client_id": "shared-client-3",
            }),
            content_type="application/json",
        )

        self.assertEqual(
            AnswerSheetEntry.objects.get(user=self.user, round=round_obj).answers[:3],
            ["Final", "Shared", ""],
        )

    def test_answer_sheet_prefills_current_user_score(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Scored Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
            score_alex=6.5,
        )

        response = self.client.get(reverse("answer_sheet"), {"date": round_obj.date.isoformat()})

        self.assertEqual(response.status_code, 200)
        round_pages = response.context["round_pages"]
        self.assertEqual(round_pages[0]["score_value"], "6.5")

    def test_answer_sheet_submit_confirmation_only_for_coop_non_creator(self):
        coop_creator_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Creator Co-op Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        coop_other_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Other Co-op Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        solo_other_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Other Solo Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        response = self.client.get(reverse("answer_sheet"), {"date": "2026-04-17"})

        self.assertEqual(response.status_code, 200)
        round_pages = {
            page["round_id"]: page
            for page in response.context["round_pages"]
        }
        self.assertFalse(round_pages[coop_creator_round.id]["submit_requires_confirmation"])
        self.assertTrue(round_pages[coop_other_round.id]["submit_requires_confirmation"])
        self.assertFalse(round_pages[solo_other_round.id]["submit_requires_confirmation"])

    def test_submit_answer_sheet_score_updates_scoresheet_score(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Submit Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "9.5",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        round_obj.refresh_from_db()
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        self.assertEqual(score_map.get("score_alex"), 9.5)
        self.assertEqual(response.json()["score_display"], "9.5")

        clear_response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "",
            }),
            content_type="application/json",
        )

        self.assertEqual(clear_response.status_code, 200)
        round_obj.refresh_from_db()
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        self.assertIsNone(score_map.get("score_alex"))

    def test_submit_answer_sheet_score_promotes_manual_override_answer_to_possible_answers(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Override Promotion Round",
            major_category="History",
            minor_category1="Presidents",
            minor_category2="",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        analysis_entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Which first U.S. president appears on the one-dollar bill?",
            answer_text="George Washington",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=round_obj,
            trivia_date=round_obj.date,
            answers=["Washington"] + [""] * 9,
            grade_overrides=[1],
        )

        response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "1",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        analysis_entry.refresh_from_db()
        self.assertIn("Washington", analysis_entry.possible_answers)
        self.assertIn("washington", analysis_entry.possible_answers)

    def test_submit_answer_sheet_score_removes_manual_rejection_answer_from_possible_answers(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Override Rejection Round",
            major_category="History",
            minor_category1="Presidents",
            minor_category2="",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        analysis_entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Which first U.S. president appears on the one-dollar bill?",
            answer_text="George Washington",
            possible_answers=["Washington", "washington", "George Washington"],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=round_obj,
            trivia_date=round_obj.date,
            answers=["Washington"] + [""] * 9,
            grade_rejections=[1],
        )

        response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "0",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        analysis_entry.refresh_from_db()
        self.assertNotIn("Washington", analysis_entry.possible_answers)
        self.assertNotIn("washington", analysis_entry.possible_answers)
        self.assertIn("George Washington", analysis_entry.possible_answers)

    def test_submit_answer_sheet_score_populates_cooperative_teammates(self):
        User.objects.create_user(username="Megan", password="pw")
        User.objects.create_user(username="Zach", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            secondary_creator="Zach",
            title="Co-op Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_zach": "score_zach",
                "score_jenny": "score_jenny",
            },
        )

        response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "8.5",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        round_obj.refresh_from_db()
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        self.assertEqual(score_map.get("score_alex"), 8.5)
        self.assertEqual(score_map.get("score_jenny"), 8.5)
        self.assertIsNone(score_map.get("score_megan"))
        self.assertIsNone(score_map.get("score_zach"))

    def test_submit_answer_sheet_score_broadcasts_shared_score_update_for_cooperative_round(self):
        User.objects.create_user(username="Megan", password="pw")
        User.objects.create_user(username="Zach", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            secondary_creator="Zach",
            title="Co-op Round Broadcast",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_zach": "score_zach",
                "score_jenny": "score_jenny",
            },
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("submit_answer_sheet_score"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "score": "8.5",
                        "client_id": "alex-device-1",
                    }),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["action"], "update")
        self.assertEqual(message["event"], "answer_sheet_submit_score")
        self.assertEqual(message["client_id"], "alex-device-1")
        self.assertEqual(message["selected_date"], trivia_date.isoformat())
        self.assertEqual(len(message["round_updates"]), 1)
        self.assertEqual(message["round_updates"][0]["id"], round_obj.id)
        self.assertEqual(
            message["round_updates"][0]["fields"],
            {
                "score_alex": 8.5,
                "score_jenny": 8.5,
            },
        )

    def test_submit_answer_sheet_score_skips_diverged_cooperative_players(self):
        User.objects.create_user(username="Megan", password="pw")
        User.objects.create_user(username="Zach", password="pw")
        User.objects.create_user(username="Jenny", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            secondary_creator="Zach",
            title="Co-op Round With Divergence",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_zach": "score_zach",
                "score_jenny": "score_jenny",
            },
        )
        diverged_user = User.objects.get(username="Jenny")
        AnswerSheetEntry.objects.create(
            user=diverged_user,
            round=round_obj,
            trivia_date=trivia_date,
            answers=["Solo"] + [""] * 9,
            is_diverged=True,
        )

        response = self.client.post(
            reverse("submit_answer_sheet_score"),
            data=json.dumps({
                "round_id": round_obj.id,
                "score": "8.5",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        round_obj.refresh_from_db()
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        self.assertEqual(score_map.get("score_alex"), 8.5)
        self.assertIsNone(score_map.get("score_megan"))
        self.assertIsNone(score_map.get("score_zach"))
        self.assertIsNone(score_map.get("score_jenny"))

    def test_answer_sheet_grade_button_reflects_analysis_availability(self):
        opted_out_creator = User.objects.create_user(username="Taylor", password="pw")
        opted_in_without_analysis = User.objects.create_user(username="Jordan", password="pw")
        matching_creator = User.objects.create_user(username="Casey", password="pw")
        ready_creator = User.objects.create_user(username="Morgan", password="pw")
        Profile.objects.filter(user=opted_out_creator).update(round_analysis_opt_in=False)
        Profile.objects.filter(user=opted_in_without_analysis).update(round_analysis_opt_in=True)
        Profile.objects.filter(user=matching_creator).update(round_analysis_opt_in=True)
        Profile.objects.filter(user=ready_creator).update(round_analysis_opt_in=True)

        trivia_date = datetime.date(2026, 4, 17)
        opted_out_round = GPTriviaRound.objects.create(
            creator="Taylor",
            title="Opted Out Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        not_analyzed_round = GPTriviaRound.objects.create(
            creator="Jordan",
            title="Needs Analysis",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        matching_round = GPTriviaRound.objects.create(
            creator="Casey",
            title="Matching Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        enabled_round = GPTriviaRound.objects.create(
            creator="Morgan",
            title="Ready Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=4,
            max_score=10,
            replay=False,
            cooperative=False,
        )

        RoundQuestionAnalysisRun.objects.create(
            round=matching_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="matching",
        )
        RoundQuestionAnalysisRun.objects.create(
            round=enabled_round,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="picture",
        )

        response = self.client.get(reverse("answer_sheet"), {"date": trivia_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        round_pages = {
            page["round_id"]: page
            for page in response.context["round_pages"]
        }
        self.assertFalse(round_pages[opted_out_round.id]["grade_enabled"])
        self.assertEqual(
            round_pages[opted_out_round.id]["grade_disabled_message"],
            "round analysis is not enabled for this creator",
        )
        self.assertFalse(round_pages[not_analyzed_round.id]["grade_enabled"])
        self.assertEqual(
            round_pages[not_analyzed_round.id]["grade_disabled_message"],
            "the round has not yet been analyzed",
        )
        self.assertTrue(round_pages[matching_round.id]["grade_enabled"])
        self.assertEqual(round_pages[matching_round.id]["grade_disabled_message"], "")
        self.assertTrue(round_pages[enabled_round.id]["grade_enabled"])
        self.assertEqual(round_pages[enabled_round.id]["grade_disabled_message"], "")

    def test_grade_answer_sheet_round_marks_correct_rows_and_returns_score(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "a zebra", "Zebra", "zebra", "Zebras", "zebras"],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="What swimming stroke was introduced to the British by Native Americans?",
            answer_text="Front crawl/freestyle",
            possible_answers=[
                "Front crawl",
                "front crawl",
                "Front-crawl",
                "front-crawl",
                "Frontcrawl",
                "frontcrawl",
                "Freestyle",
                "freestyle",
                "Free style",
                "free style",
                "Front crawl or freestyle",
                "front crawl or freestyle",
            ],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=3,
            question_text="Which choice is correct?",
            answer_text="All of those",
            possible_answers=["All of those", "all of those", "All", "all", "All of the above", "all of the above"],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "   zebra   tentative guess\nFront crawl   alternate wording\nWrong answer\n",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 2)
        self.assertEqual(payload["score_display"], "2")
        self.assertEqual(payload["row_results"][0]["submitted_text"], "zebra")
        self.assertEqual(payload["row_results"][0]["state"], "correct")
        self.assertEqual(payload["row_results"][1]["submitted_text"], "Front crawl")
        self.assertEqual(payload["row_results"][1]["state"], "correct")
        self.assertEqual(payload["row_results"][2]["submitted_text"], "Wrong answer")
        self.assertEqual(payload["row_results"][2]["state"], "incorrect")
        self.assertEqual(payload["row_results"][3]["state"], "blank")

    def test_override_answer_sheet_grade_marks_specific_row_correct(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Override Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("override_answer_sheet_grade"),
            data=json.dumps({
                "round_id": round_obj.id,
                "question_number": 1,
                "answers": ["Wrong answer"] + [""] * 9,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 1)
        self.assertEqual(payload["row_results"][0]["state"], "correct")
        self.assertEqual(payload["grade_overrides"], [1])
        entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertEqual(entry.grade_overrides, [1])
        self.assertEqual(entry.grade_rejections, [])
        self.assertEqual(entry.answers[0], "Wrong answer")

    def test_override_answer_sheet_grade_marks_specific_row_incorrect(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Override Reject Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("override_answer_sheet_grade"),
            data=json.dumps({
                "round_id": round_obj.id,
                "question_number": 1,
                "mode": "incorrect",
                "answers": ["Zebra"] + [""] * 9,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 0)
        self.assertEqual(payload["row_results"][0]["state"], "incorrect")
        self.assertEqual(payload["grade_overrides"], [])
        self.assertEqual(payload["grade_rejections"], [1])
        entry = AnswerSheetEntry.objects.get(user=self.user, round=round_obj)
        self.assertEqual(entry.grade_overrides, [])
        self.assertEqual(entry.grade_rejections, [1])
        self.assertEqual(entry.answers[0], "Zebra")

    def test_grade_answer_sheet_round_tolerates_punctuation_initialisms_and_one_char_typos(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Flexible Grade Round",
            major_category="History",
            minor_category1="People",
            minor_category2="Film",
            date=datetime.date(2026, 4, 17),
            round_number=2,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Which Best Picture winner stars Colin Firth as King George VI?",
            answer_text="King's Speech",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="Which founding father appears on the $100 bill?",
            answer_text="Benjamin Franklin",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=3,
            question_text="Name the Star Wars sequel released in 1980.",
            answer_text="Star Wars: The Empire Strikes Back",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "The kings speech\nbf\nesb\n",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 3)
        self.assertEqual(payload["row_results"][0]["state"], "correct")
        self.assertEqual(payload["row_results"][1]["state"], "correct")
        self.assertEqual(payload["row_results"][2]["state"], "correct")

    def test_grade_answer_sheet_round_does_not_allow_one_char_typos_for_short_or_numeric_answers(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Strict Short Answers Round",
            major_category="History",
            minor_category1="People",
            minor_category2="Numbers",
            date=datetime.date(2026, 4, 17),
            round_number=3,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Use the abbreviation for Benjamin Franklin.",
            answer_text="Benjamin Franklin",
            possible_answers=["BF"],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="What is the answer to life, the universe, and everything?",
            answer_text="42",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=3,
            question_text="Name the Swedish band.",
            answer_text="ABBA",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "BJ\n43\nABBB\n",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 0)
        self.assertEqual(payload["row_results"][0]["state"], "incorrect")
        self.assertEqual(payload["row_results"][1]["state"], "incorrect")
        self.assertEqual(payload["row_results"][2]["state"], "incorrect")

    def test_grade_answer_sheet_round_allows_long_word_typos_but_not_short_words_and_plain_numbers(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Word Level Typo Round",
            major_category="History",
            minor_category1="People",
            minor_category2="Numbers",
            date=datetime.date(2026, 4, 18),
            round_number=4,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Which founding father appears on the $100 bill?",
            answer_text="Benjamin Franklin",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=2,
            question_text="Name the Tolstoy novel.",
            answer_text="War and Peace",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=3,
            question_text="What is the answer to life, the universe, and everything?",
            answer_text="42",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=4,
            question_text="Within the accepted numeric tolerance, what measurement was recorded?",
            answer_text="100 +/- 5",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=5,
            question_text="Outside the accepted numeric tolerance, what measurement was recorded?",
            answer_text="100 +/- 5",
            possible_answers=[],
            round_type="text",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Benjomin Franklon\nBar and Peace\n43\n103\n106\n",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 2)
        self.assertEqual(payload["row_results"][0]["state"], "correct")
        self.assertEqual(payload["row_results"][1]["state"], "incorrect")
        self.assertEqual(payload["row_results"][2]["state"], "incorrect")
        self.assertEqual(payload["row_results"][3]["state"], "correct")
        self.assertEqual(payload["row_results"][4]["state"], "incorrect")

    def test_grade_answer_sheet_round_accepts_matching_rounds(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Matching Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="matching",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="Match Alex to the right position.",
            answer_text="Alex - Defender",
            possible_answers=["Defender", "defender", "C", "c", "3", "third"],
            round_type="matching",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Defender",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 1)
        self.assertEqual(payload["row_results"][0]["state"], "correct")

    def test_grade_answer_sheet_round_accepts_multiple_choice_letters_without_stored_aliases(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="multiple choice",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text=(
                "Which answer is correct?\n"
                "A. Alpha wave\n"
                "B. Beta decay\n"
                "C. Gamma ray\n"
                "D. Delta blues"
            ),
            answer_text="Gamma ray",
            possible_answers=[],
            round_type="multiple choice",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "C",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 1)
        self.assertEqual(payload["row_results"][0]["state"], "correct")

    def test_grade_answer_sheet_round_accepts_multiple_choice_letters_for_hyphenated_round_type(self):
        round_obj = GPTriviaRound.objects.create(
            creator="Alex",
            title="Multiple Choice Hyphen Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 4, 17),
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=False,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="multiple-choice",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text=(
                "Which answer is correct?\n"
                "A. Alpha wave\n"
                "B. Beta decay\n"
                "C. Gamma ray\n"
                "D. Delta blues"
            ),
            answer_text="Gamma ray",
            possible_answers=[],
            round_type="multiple-choice",
            player_correctness={"Alex": ""},
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "C",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["score"], 1)
        self.assertEqual(payload["row_results"][0]["state"], "correct")

    def test_grade_answer_sheet_round_broadcasts_for_shared_coop_round(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("grade_answer_sheet_round"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "answers": "Zebra",
                        "client_id": "grade-client-1",
                    }),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["shared"])
        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["action"], "answer_sheet")
        self.assertEqual(message["event"], "answer_sheet_grade")
        self.assertEqual(message["client_id"], "grade-client-1")
        self.assertEqual(message["score_display"], "1")
        self.assertEqual(message["answers"][:1], ["Zebra"])
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=self.user, round=round_obj).answers[:1],
            ["Zebra"],
        )
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=megan, round=round_obj).answers[:1],
            ["Zebra"],
        )

    def test_override_answer_sheet_grade_broadcasts_for_shared_coop_round(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Override Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("override_answer_sheet_grade"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "question_number": 1,
                        "answers": ["Wrong answer"] + [""] * 9,
                        "client_id": "override-client-1",
                    }),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["shared"])
        self.assertEqual(payload["score"], 1)
        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["event"], "answer_sheet_grade")
        self.assertEqual(message["client_id"], "override-client-1")
        self.assertEqual(message["grade_overrides"], [1])
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=self.user, round=round_obj).grade_overrides,
            [1],
        )
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=megan, round=round_obj).grade_overrides,
            [1],
        )

    def test_override_answer_sheet_grade_rejection_broadcasts_for_shared_coop_round(self):
        megan = User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Shared Reject Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        MergedPresentation.objects.create(
            name=trivia_date.strftime("%m.%d.%Y"),
            presentation_id="",
            player_list={
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("override_answer_sheet_grade"),
                    data=json.dumps({
                        "round_id": round_obj.id,
                        "question_number": 1,
                        "mode": "incorrect",
                        "answers": ["Zebra"] + [""] * 9,
                        "client_id": "override-client-2",
                    }),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["shared"])
        self.assertEqual(payload["score"], 0)
        self.assertEqual(payload["grade_rejections"], [1])
        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["event"], "answer_sheet_grade")
        self.assertEqual(message["client_id"], "override-client-2")
        self.assertEqual(message["grade_rejections"], [1])
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=self.user, round=round_obj).grade_rejections,
            [1],
        )
        self.assertEqual(
            AnswerSheetEntry.objects.get(user=megan, round=round_obj).grade_rejections,
            [1],
        )

    def test_grade_answer_sheet_round_does_not_broadcast_for_diverged_coop_round(self):
        User.objects.create_user(username="Megan", password="pw")
        trivia_date = datetime.date(2026, 4, 17)
        round_obj = GPTriviaRound.objects.create(
            creator="Megan",
            title="Diverged Grade Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=trivia_date,
            round_number=1,
            max_score=10,
            replay=False,
            cooperative=True,
        )
        run = RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="text",
        )
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=round_obj,
            round_name=round_obj.title,
            round_date=round_obj.date,
            question_number=1,
            question_text="What animal is white with black stripes?",
            answer_text="A Zebra",
            possible_answers=["A Zebra", "Zebra", "zebra"],
            round_type="text",
            player_correctness={"Alex": "", "Megan": ""},
        )
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=round_obj,
            trivia_date=trivia_date,
            answers=["Zebra"] + [""] * 9,
            is_diverged=True,
        )

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            response = self.client.post(
                reverse("grade_answer_sheet_round"),
                data=json.dumps({
                    "round_id": round_obj.id,
                    "answers": "Zebra",
                    "client_id": "grade-client-2",
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["shared"])
        broadcast.assert_not_called()
