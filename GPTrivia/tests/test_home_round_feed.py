import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import GPTriviaRound, MergedPresentation


class HomeRoundFeedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="Alex", password="pw")
        self.client.force_login(self.user)

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_returns_new_and_historical_rounds(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://example.com/new-round"],
            ["Fresh Round"],
            ["Ichigo"],
            ["https://example.com/source-round"],
            ["2026-03-14"],
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Historic Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date=datetime.date(2026, 3, 1),
            round_number=1,
            max_score=10,
            cooperative=True,
            link="https://example.com/historic-round",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["rounds"]), 2)
        self.assertEqual(payload["rounds"][0]["title"], "Fresh Round")
        self.assertTrue(payload["rounds"][0]["is_new"])
        self.assertFalse(payload["rounds"][0]["coop"])
        self.assertEqual(payload["rounds"][1]["title"], "Historic Round")
        self.assertFalse(payload["rounds"][1]["is_new"])
        self.assertTrue(payload["rounds"][1]["coop"])
        self.assertEqual(payload["rounds"][1]["shared_date"], "2026-03-01")

    def test_home_page_contains_new_column_and_search_controls(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search by creator, round title, or date")
        self.assertContains(response, "Page 1 of 1")
        self.assertContains(response, ">New<", html=False)
        self.assertNotContains(response, "Past rounds are display-only for now.")

    @patch(
        "GPTrivia.views.create_presentation",
        return_value=(
            "presentation-generated",
            ["Alex"],
            ["Historic Flags"],
            ["https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.copied-round"],
        ),
    )
    def test_generate_accepts_historical_round_selection_and_stores_copied_link(self, create_mock):
        with patch("GPTrivia.views._current_trivia_date", return_value=datetime.date(2026, 3, 14)):
            response = self.client.post(
                reverse("home"),
                data={
                    "action": "generate",
                    "round_order_0": "1",
                    "round_title_0": "Historic Flags",
                    "round_creator_0": "Alex",
                    "round_link_0": "https://docs.google.com/presentation/d/source-merged/edit#slide=id.round-start",
                    "round_old_link_0": "https://docs.google.com/presentation/d/source-merged/edit#slide=id.round-start",
                    "round_shared_date_0": "2025-05-26",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertEqual(
            create_mock.call_args.args[2],
            ["https://docs.google.com/presentation/d/source-merged/edit#slide=id.round-start"],
        )

        generated_presentation = MergedPresentation.objects.get(presentation_id="presentation-generated")
        self.assertEqual(generated_presentation.round_names, ["Historic Flags"])

        stored_round = GPTriviaRound.objects.get(date=datetime.date(2026, 3, 14))
        self.assertEqual(
            stored_round.link,
            "https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.copied-round",
        )
