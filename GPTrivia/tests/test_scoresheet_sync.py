import datetime
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import GPTriviaRound, MergedPresentation


class ScoresheetSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="test-pass")
        self.client.force_login(self.user)
        self.round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Round 1",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Astronomy",
            date=datetime.date(2026, 3, 12),
            round_number=1,
            max_score=10,
            score_alex=5,
            score_megan=7,
            replay=False,
            cooperative=False,
            notes="Original notes",
            link="https://example.com/round-1",
        )
        self.presentation = MergedPresentation.objects.create(
            name="03.12.2026",
            presentation_id="presentation-1",
            round_names=["Round 1"],
            creator_list=["Alex"],
            joker_round_indices={"alex": "Round 1"},
            player_list={"score_alex": "score_alex", "score_megan": "score_megan"},
            host="Alex",
            scorekeeper="Megan",
            style_points={"Alex": 1},
            notes="Old presentation notes",
            tiebreak_winner="Alex",
            crowned_winner="Jenny",
        )

    def test_patch_save_updates_only_changed_fields_and_broadcasts_after_commit(self):
        payload = {
            "presentation_id": self.presentation.presentation_id,
            "selected_date": "2026-03-12",
            "client_id": "client-1",
            "mutation_id": "mutation-1",
            "round_updates": [
                {
                    "id": self.round.id,
                    "fields": {
                        "score_alex": 8.5,
                        "cooperative": True,
                    },
                }
            ],
            "presentation_updates": {
                "host": "Jenny",
                "notes": "Updated presentation notes",
                "crowned_winner": "Megan",
            },
        }

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.post(
                    reverse("save_scores"),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(callbacks), 1)
            broadcast.assert_not_called()

            self.round.refresh_from_db()
            self.presentation.refresh_from_db()

            self.assertEqual(self.round.score_alex, 8.5)
            self.assertTrue(self.round.cooperative)
            self.assertEqual(self.round.title, "Round 1")
            self.assertEqual(self.round.notes, "Original notes")

            self.assertEqual(self.presentation.host, "Jenny")
            self.assertEqual(self.presentation.notes, "Updated presentation notes")
            self.assertEqual(self.presentation.scorekeeper, "Megan")
            self.assertEqual(self.presentation.crowned_winner, "Megan")
            self.assertEqual(self.presentation.round_names, ["Round 1"])

            callbacks[0]()
            broadcast.assert_called_once()
            message = broadcast.call_args.args[0]
            self.assertEqual(message["action"], "update")
            self.assertEqual(message["event"], "save_scores")
            self.assertEqual(message["client_id"], "client-1")
            self.assertEqual(message["mutation_id"], "mutation-1")
            self.assertEqual(message["round_updates"], payload["round_updates"])
            self.assertEqual(message["presentation_updates"], payload["presentation_updates"])

    def test_patch_save_rejects_invalid_round_field(self):
        payload = {
            "presentation_id": self.presentation.presentation_id,
            "selected_date": "2026-03-12",
            "client_id": "client-1",
            "mutation_id": "mutation-2",
            "round_updates": [
                {
                    "id": self.round.id,
                    "fields": {
                        "not_a_real_field": "bad",
                    },
                }
            ],
            "presentation_updates": {},
        }

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.post(
                    reverse("save_scores"),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(callbacks, [])
        broadcast.assert_not_called()

    def test_patch_save_persists_dynamic_player_scores_in_extra_scores(self):
        payload = {
            "presentation_id": self.presentation.presentation_id,
            "selected_date": "2026-03-12",
            "client_id": "client-1",
            "mutation_id": "mutation-dynamic-save",
            "round_updates": [
                {
                    "id": self.round.id,
                    "fields": {
                        "extra_scores": {
                            "score_guest": 9,
                        },
                    },
                }
            ],
            "presentation_updates": {
                "player_list": {
                    "score_alex": "score_alex",
                    "score_megan": "score_megan",
                    "score_guest": "score_guest",
                },
            },
        }

        response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.round.refresh_from_db()
        self.presentation.refresh_from_db()
        self.assertEqual(self.round.extra_scores, {"score_guest": 9})
        self.assertEqual(
            self.presentation.player_list,
            {
                "score_alex": "score_alex",
                "score_megan": "score_megan",
                "score_guest": "score_guest",
            },
        )

    def test_patch_save_removes_deleted_dynamic_player_scores(self):
        self.round.extra_scores = {"score_guest": 9}
        self.round.save(update_fields=["extra_scores"])
        self.presentation.player_list = {
            "score_alex": "score_alex",
            "score_megan": "score_megan",
            "score_guest": "score_guest",
        }
        self.presentation.save(update_fields=["player_list"])

        payload = {
            "presentation_id": self.presentation.presentation_id,
            "selected_date": "2026-03-12",
            "client_id": "client-1",
            "mutation_id": "mutation-dynamic-remove",
            "round_updates": [
                {
                    "id": self.round.id,
                    "fields": {
                        "extra_scores": {},
                    },
                }
            ],
            "presentation_updates": {
                "player_list": {
                    "score_alex": "score_alex",
                    "score_megan": "score_megan",
                },
            },
        }

        response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.round.refresh_from_db()
        self.presentation.refresh_from_db()
        self.assertEqual(self.round.extra_scores, {})
        self.assertEqual(
            self.presentation.player_list,
            {
                "score_alex": "score_alex",
                "score_megan": "score_megan",
            },
        )

    def test_analysis_views_include_dynamic_players(self):
        self.round.extra_scores = {"score_guest": 9}
        self.round.save(update_fields=["extra_scores"])
        self.presentation.player_list = {
            "score_alex": "score_alex",
            "score_megan": "score_megan",
            "score_guest": "score_guest",
        }
        self.presentation.save(update_fields=["player_list"])

        analysis_response = self.client.get(reverse("player_analysis"))
        rounds_response = self.client.get(reverse("rounds_list"))

        self.assertEqual(analysis_response.status_code, 200)
        self.assertIn("Guest", analysis_response.context["players"])
        self.assertEqual(analysis_response.context["mapping"]["Guest"], "score_guest")

        self.assertEqual(rounds_response.status_code, 200)
        self.assertIn("score_guest", rounds_response.context["player_fields"])

    def test_create_round_broadcasts_identity_after_commit(self):
        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.post(
                    reverse("create_round", args=["2026-03-12", 2]),
                    data=json.dumps({
                        "client_id": "client-2",
                        "mutation_id": "mutation-3",
                    }),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(callbacks), 1)
            created_round = GPTriviaRound.objects.get(round_number=2, date=datetime.date(2026, 3, 12))
            callbacks[0]()

        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["event"], "create_round")
        self.assertEqual(message["client_id"], "client-2")
        self.assertEqual(message["mutation_id"], "mutation-3")
        self.assertEqual(message["round_id"], created_round.id)

    def test_delete_round_broadcasts_identity_after_commit(self):
        round_id = self.round.id

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.client.delete(
                    reverse("delete_round", args=[round_id]),
                    data=json.dumps({
                        "client_id": "client-3",
                        "mutation_id": "mutation-4",
                    }),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(callbacks), 1)
            self.assertFalse(GPTriviaRound.objects.filter(id=round_id).exists())
            callbacks[0]()

        broadcast.assert_called_once()
        message = broadcast.call_args.args[0]
        self.assertEqual(message["event"], "delete_round")
        self.assertEqual(message["client_id"], "client-3")
        self.assertEqual(message["mutation_id"], "mutation-4")
        self.assertEqual(message["round_id"], round_id)
