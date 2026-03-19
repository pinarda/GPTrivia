import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import GPTriviaRound


class AnalysisVisibilityThresholdTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="test-pass")
        self.client.force_login(self.user)

        start_date = datetime.date(2025, 1, 1)
        for round_number in range(50):
            round_obj = GPTriviaRound.objects.create(
                creator="Alex",
                title=f"Round {round_number + 1}",
                major_category="Science",
                minor_category1="Physics",
                minor_category2="Space",
                date=start_date + datetime.timedelta(days=round_number),
                round_number=round_number + 1,
                max_score=10,
                score_alex=8,
            )
            if round_number < 49:
                round_obj.extra_scores = {"score_guest player": 6}
                round_obj.save(update_fields=["extra_scores"])

    def test_rounds_list_hides_players_below_threshold(self):
        response = self.client.get(reverse("rounds_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("score_alex", response.context["player_fields"])
        self.assertNotIn("score_guest player", response.context["player_fields"])
        self.assertContains(response, f'{reverse("scoresheet_new")}?date=2025-01-01')

    def test_player_analysis_hides_players_below_threshold(self):
        response = self.client.get(reverse("player_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Alex", response.context["players"])
        self.assertNotIn("Guest Player", response.context["players"])

    def test_player_profile_requires_minimum_round_threshold(self):
        eligible_response = self.client.get(reverse("player_profile", args=["Alex"]))
        hidden_response = self.client.get(reverse("player_profile", args=["Guest Player"]))

        self.assertEqual(eligible_response.status_code, 200)
        self.assertEqual(hidden_response.status_code, 404)

    def test_player_analysis_plot_rejects_sub_threshold_player(self):
        response = self.client.get(
            reverse("player_analysis_plot"),
            {
                "chart_type": "player_bar",
                "player": "Guest Player",
            },
        )

        self.assertEqual(response.status_code, 400)
