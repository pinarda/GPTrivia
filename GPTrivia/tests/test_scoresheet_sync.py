import datetime
import json
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from GPTrivia.models import AnswerSheetEntry, GPTriviaRound, MergedPresentation
from GPTrivia.player_scores import get_round_score_map


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

    def test_scoresheet_template_references_current_built_bundle(self):
        build_directory = Path(settings.BASE_DIR) / "scoresheet" / "build"
        manifest = json.loads((build_directory / "asset-manifest.json").read_text())
        javascript_bundle = manifest["files"]["main.js"].lstrip("/")

        response = self.client.get(reverse("scoresheet_new"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertContains(response, f"scoresheet/build/{javascript_bundle}")
        self.assertContains(response, "onerror=\"retryScoresheetBundleLoad()\"")
        self.assertContains(
            response,
            "/static/jquery-tabledit-1.2.3/jquery.tabledit.min.js",
        )
        self.assertTrue((build_directory / javascript_bundle).is_file())

    def test_patch_save_updates_only_changed_fields_and_broadcasts_after_commit(self):
        AnswerSheetEntry.objects.create(
            user=self.user,
            round=self.round,
            trivia_date=self.round.date,
            answers=["Private answer"],
            is_diverged=True,
        )
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
            self.assertFalse(
                AnswerSheetEntry.objects.get(user=self.user, round=self.round).is_diverged
            )
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
            self.assertEqual(message["cooperative_updates"], [{
                "id": self.round.id,
                "cooperative": True,
                "selected_date": "2026-03-12",
            }])
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

    def test_cooperative_broadcast_uses_canonical_round_date_when_client_date_is_blank(self):
        payload = {
            "presentation_id": self.presentation.presentation_id,
            "selected_date": "",
            "client_id": "client-coop-toggle",
            "mutation_id": "mutation-coop-toggle",
            "round_updates": [{
                "id": self.round.id,
                "fields": {"cooperative": True},
            }],
            "presentation_updates": {},
        }

        with patch("GPTrivia.views._broadcast_scoresheet_message") as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("save_scores"),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        message = broadcast.call_args.args[0]
        self.assertEqual(message["selected_date"], "")
        self.assertEqual(message["cooperative_updates"], [{
            "id": self.round.id,
            "cooperative": True,
            "selected_date": self.round.date.isoformat(),
        }])

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

    @patch("GPTrivia.views.MIN_ANALYSIS_ROUNDS", 1)
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

    def test_extra_score_helper_ignores_corrupted_numeric_keys(self):
        self.round.extra_scores = "{'score_bobo the dodo': 8, '0': '{', '1': '}'}"

        score_map = get_round_score_map(self.round)

        self.assertEqual(score_map["score_bobo the dodo"], 8)
        self.assertNotIn("score_0", score_map)
        self.assertNotIn("score_1", score_map)

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

    def test_delete_round_removes_matching_presentation_with_non_padded_name(self):
        self.presentation.delete()
        unpadded_presentation = MergedPresentation.objects.create(
            name="3.12.2026",
            presentation_id="presentation-unpadded",
            round_names=["Round 1"],
            creator_list=["Alex"],
            joker_round_indices={},
            player_list={"score_alex": "score_alex"},
            host="Alex",
            scorekeeper="Megan",
            style_points={},
            notes="",
            tiebreak_winner="",
            crowned_winner="",
        )

        response = self.client.delete(
            reverse("delete_round", args=[self.round.id]),
            data=json.dumps({
                "client_id": "client-5",
                "mutation_id": "mutation-6",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GPTriviaRound.objects.filter(date=datetime.date(2026, 3, 12)).exists())
        self.assertFalse(MergedPresentation.objects.filter(id=unpadded_presentation.id).exists())

    def test_patch_save_does_not_create_blank_presentation_placeholder(self):
        MergedPresentation.objects.all().delete()

        payload = {
            "presentation_id": "",
            "selected_date": "2026-03-21",
            "client_id": "client-placeholder",
            "mutation_id": "mutation-placeholder",
            "round_updates": [],
            "presentation_updates": {
                "host": "Jenny",
                "notes": "Should not create placeholder presentation",
            },
        }

        response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MergedPresentation.objects.count(), 0)

    def test_patch_save_creates_presentation_for_new_night_with_rounds(self):
        MergedPresentation.objects.all().delete()
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Round 1",
            major_category="History",
            minor_category1="Modern",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
        )

        payload = {
            "presentation_id": "",
            "selected_date": "2026-03-20",
            "client_id": "client-new-night",
            "mutation_id": "mutation-new-night",
            "round_updates": [],
            "presentation_updates": {
                "host": "Alex",
                "scorekeeper": "Megan",
                "crowned_winner": "Jenny",
                "notes": "Fresh night winner saved",
            },
        }

        response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        saved_presentation = MergedPresentation.objects.get(name="03.20.2026")
        self.assertEqual(saved_presentation.presentation_id, "")
        self.assertEqual(saved_presentation.host, "Alex")
        self.assertEqual(saved_presentation.scorekeeper, "Megan")
        self.assertEqual(saved_presentation.crowned_winner, "Jenny")
        self.assertEqual(saved_presentation.notes, "Fresh night winner saved")

    def test_blank_id_scoresheet_presentation_is_reused_and_returned_by_meta(self):
        MergedPresentation.objects.all().delete()
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Round 1",
            major_category="History",
            minor_category1="Modern",
            minor_category2="",
            date=datetime.date(2026, 3, 20),
            round_number=1,
            max_score=10,
        )

        create_payload = {
            "presentation_id": "",
            "selected_date": "2026-03-20",
            "client_id": "client-blank-meta-1",
            "mutation_id": "mutation-blank-meta-1",
            "round_updates": [],
            "presentation_updates": {
                "host": "Alex",
                "crowned_winner": "Jenny",
            },
        }
        update_payload = {
            "presentation_id": "",
            "selected_date": "2026-03-20",
            "client_id": "client-blank-meta-2",
            "mutation_id": "mutation-blank-meta-2",
            "round_updates": [],
            "presentation_updates": {
                "scorekeeper": "Megan",
                "notes": "Returned by meta",
            },
        }

        first_response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(update_payload),
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(MergedPresentation.objects.filter(name="03.20.2026").count(), 1)

        response = self.client.get(reverse("scoresheet_presentation_meta"), {"date": "2026-03-20"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_presentation"]["name"], "03.20.2026")
        self.assertEqual(payload["selected_presentation"]["presentation_id"], "")
        self.assertEqual(payload["selected_presentation"]["crowned_winner"], "Jenny")
        self.assertEqual(payload["selected_presentation"]["scorekeeper"], "Megan")
        self.assertEqual(payload["selected_presentation"]["notes"], "Returned by meta")
        self.assertIn(
            ("03.20.2026", "Jenny"),
            [(item["name"], item["crowned_winner"]) for item in payload["crown_history"]],
        )

    def test_patch_save_prefers_selected_date_when_presentation_id_is_duplicated(self):
        older_duplicate = MergedPresentation.objects.create(
            name="05.05.2023",
            presentation_id="presentation-duplicate",
            round_names=["Old Round"],
            creator_list=["Megan"],
            joker_round_indices={},
            player_list={"score_megan": "score_megan"},
            host="Old Host",
            scorekeeper="Old Scorekeeper",
            style_points={},
            notes="older duplicate",
            tiebreak_winner="",
            crowned_winner="",
        )
        target_duplicate = MergedPresentation.objects.create(
            name="05.12.2023",
            presentation_id="presentation-duplicate",
            round_names=["Target Round"],
            creator_list=["Alex"],
            joker_round_indices={},
            player_list={"score_alex": "score_alex"},
            host="Alex",
            scorekeeper="Megan",
            style_points={},
            notes="target duplicate",
            tiebreak_winner="",
            crowned_winner="",
        )

        payload = {
            "presentation_id": "presentation-duplicate",
            "selected_date": "2023-05-12",
            "client_id": "client-dup",
            "mutation_id": "mutation-dup",
            "round_updates": [],
            "presentation_updates": {
                "host": "Jenny",
                "notes": "updated duplicate target",
            },
        }

        response = self.client.post(
            reverse("save_scores"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        older_duplicate.refresh_from_db()
        target_duplicate.refresh_from_db()
        self.assertEqual(older_duplicate.host, "Old Host")
        self.assertEqual(older_duplicate.notes, "older duplicate")
        self.assertEqual(target_duplicate.host, "Jenny")
        self.assertEqual(target_duplicate.notes, "updated duplicate target")

    def test_scoresheet_bootstrap_returns_requested_date_only(self):
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Round 2",
            major_category="History",
            minor_category1="Modern",
            minor_category2="Flags",
            date=datetime.date(2026, 3, 19),
            round_number=1,
            max_score=10,
        )

        response = self.client.get(reverse("scoresheet_bootstrap"), {"date": "2026-03-12"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_date"], "2026-03-12")
        self.assertEqual(payload["dates"], ["2026-03-19", "2026-03-12"])
        self.assertEqual([round_data["id"] for round_data in payload["rounds"]], [self.round.id])
        self.assertIn("Alex", payload["creator_options"])
        self.assertIn("Megan", payload["creator_options"])
        self.assertIn("Science", payload["major_categories"])
        self.assertIn("History", payload["major_categories"])
        self.assertIn("Physics", payload["minor_categories"])
        self.assertIn("Flags", payload["minor_categories"])

    def test_scoresheet_bootstrap_allows_valid_requested_date_without_rounds(self):
        response = self.client.get(reverse("scoresheet_bootstrap"), {"date": "2026-03-20"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_date"], "2026-03-20")
        self.assertEqual(payload["dates"], ["2026-03-12"])
        self.assertEqual(payload["rounds"], [])

    def test_scoresheet_presentation_meta_returns_selected_presentation_and_history(self):
        older_presentation = MergedPresentation.objects.create(
            name="03.05.2026",
            presentation_id="presentation-older",
            crowned_winner="Alex",
            status=MergedPresentation.STATUS_READY,
        )

        response = self.client.get(reverse("scoresheet_presentation_meta"), {"date": "2026-03-12"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_presentation"]["presentation_id"], self.presentation.presentation_id)
        self.assertEqual(
            [(item["name"], item["crowned_winner"]) for item in payload["crown_history"]],
            [(older_presentation.name, "Alex"), (self.presentation.name, "Jenny")],
        )
