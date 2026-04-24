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

        other_client = self.client_class()
        other_client.force_login(jenny)
        shared_response = other_client.get(reverse("answer_sheet"), {"date": trivia_date.isoformat()})
        self.assertEqual(shared_response.status_code, 200)
        round_pages = shared_response.context["round_pages"]
        self.assertEqual(round_pages[0]["answers"][:4], ["One", "Two", "Three", ""])

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
        self.assertFalse(round_pages[matching_round.id]["grade_enabled"])
        self.assertEqual(
            round_pages[matching_round.id]["grade_disabled_message"],
            "grading this round type is not currently enabled",
        )
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

    def test_grade_answer_sheet_round_rejects_matching_round(self):
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
        RoundQuestionAnalysisRun.objects.create(
            round=round_obj,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
            round_type="matching",
        )

        response = self.client.post(
            reverse("grade_answer_sheet_round"),
            data=json.dumps({
                "round_id": round_obj.id,
                "answers": "Anything",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "grading this round type is not currently enabled",
        )

    def test_grade_answer_sheet_round_broadcasts_for_shared_coop_round(self):
        User.objects.create_user(username="Megan", password="pw")
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
