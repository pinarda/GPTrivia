import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from GPTrivia import views
from GPTrivia.models import GPTriviaRound, HomePresentationBuildJob, MergedPresentation, SubmittedRound


class HomeRoundFeedTests(TestCase):
    def setUp(self):
        cache.clear()
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
        self.assertContains(response, "const scoresheetBaseUrl")
        self.assertContains(response, "home-date-link")
        self.assertContains(response, "is_new: Boolean(round.is_new)")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_overlays_submitted_round_metadata_on_gmail_rounds(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["Shared Deck Title"],
            ["hailsciencetrivia@gmail.com"],
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["2026-03-15"],
        )
        SubmittedRound.objects.create(
            presentation_id="swoop-123",
            title="Winged Science",
            creator="Alex",
            cooperative=True,
            link="https://docs.google.com/presentation/d/swoop-123/edit",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Winged Science")
        self.assertEqual(round_payload["source_title"], "Shared Deck Title")
        self.assertEqual(round_payload["creator"], "Alex")
        self.assertTrue(round_payload["coop"])
        self.assertEqual(round_payload["presentation_id"], "swoop-123")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_save_available_round_metadata_persists_across_gmail_refresh(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["Shared Deck Title"],
            ["hailsciencetrivia@gmail.com"],
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["2026-03-15"],
        )

        save_response = self.client.post(
            reverse("save_available_round_metadata"),
            data={
                "title": "Winged Science",
                "source_title": "Shared Deck Title",
                "creator": "Alex",
                "link": "https://docs.google.com/presentation/d/swoop-123/edit",
                "old_link": "https://docs.google.com/presentation/d/swoop-123/edit",
                "coop": True,
            },
            content_type="application/json",
        )

        self.assertEqual(save_response.status_code, 200)
        saved_round = SubmittedRound.objects.get(presentation_id="swoop-123")
        self.assertEqual(saved_round.title, "Winged Science")
        self.assertEqual(saved_round.source_title, "Shared Deck Title")
        self.assertEqual(saved_round.creator, "Alex")
        self.assertTrue(saved_round.cooperative)

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Winged Science")
        self.assertEqual(round_payload["source_title"], "Shared Deck Title")
        self.assertEqual(round_payload["creator"], "Alex")
        self.assertTrue(round_payload["coop"])

    @patch("GPTrivia.views._infer_available_round_title_from_first_slide", return_value="GPT Identified Title")
    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_identifies_opted_in_creator_round_title_once(
        self,
        mock_get_round_titles_and_links,
        mock_infer_title,
    ):
        creator_user = User.objects.create_user(username="Megan", password="pw")
        creator_user.profile.round_analysis_opt_in = True
        creator_user.profile.save(update_fields=["round_analysis_opt_in"])

        mock_get_round_titles_and_links.return_value = (
            ["https://docs.google.com/presentation/d/swoop-456/edit"],
            ["First Slide Fallback"],
            ["Megan"],
            ["https://docs.google.com/presentation/d/swoop-456/edit"],
            ["2026-03-16"],
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "GPT Identified Title")
        self.assertEqual(round_payload["source_title"], "GPT Identified Title")
        self.assertEqual(round_payload["creator"], "Megan")
        saved_round = SubmittedRound.objects.get(presentation_id="swoop-456")
        self.assertEqual(saved_round.title, "GPT Identified Title")
        self.assertEqual(saved_round.source_title, "GPT Identified Title")
        mock_infer_title.assert_called_once()

    @patch("GPTrivia.views._infer_available_round_title_from_first_slide")
    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_reuses_persisted_identified_title_without_reinferring(
        self,
        mock_get_round_titles_and_links,
        mock_infer_title,
    ):
        creator_user = User.objects.create_user(username="Megan", password="pw")
        creator_user.profile.round_analysis_opt_in = True
        creator_user.profile.save(update_fields=["round_analysis_opt_in"])

        mock_get_round_titles_and_links.return_value = (
            ["https://docs.google.com/presentation/d/swoop-789/edit"],
            ["First Slide Fallback"],
            ["Megan"],
            ["https://docs.google.com/presentation/d/swoop-789/edit"],
            ["2026-03-17"],
        )
        SubmittedRound.objects.create(
            presentation_id="swoop-789",
            title="Manual Edited Title",
            source_title="GPT Identified Title",
            creator="Megan",
            cooperative=False,
            link="https://docs.google.com/presentation/d/swoop-789/edit",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Manual Edited Title")
        self.assertEqual(round_payload["source_title"], "GPT Identified Title")
        mock_infer_title.assert_not_called()

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_only_shows_available_rounds_from_unread_gmail(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = ([], [], [], [], [])
        SubmittedRound.objects.create(
            presentation_id="pending-123",
            title="Fresh Swoop Round",
            creator="Megan",
            cooperative=False,
            link="https://docs.google.com/presentation/d/pending-123/edit",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rounds"], [])

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_dedupes_submitted_round_when_gmail_link_shape_differs(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://mail.google.com/share-link-that-does-not-preserve-id"],
            ["Winged Science"],
            ["Unknown"],
            ["https://mail.google.com/share-link-that-does-not-preserve-id"],
            ["2026-03-15"],
        )
        SubmittedRound.objects.create(
            presentation_id="swoop-123",
            title="Winged Science",
            creator="Alex",
            cooperative=True,
            link="https://docs.google.com/presentation/d/swoop-123/edit",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["rounds"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title"], "Winged Science")
        self.assertEqual(payload[0]["creator"], "Alex")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_does_not_overlay_title_only_match_when_creator_differs(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://mail.google.com/new-share-link"],
            ["Rhyming Picture Round"],
            ["Megan"],
            ["https://mail.google.com/new-share-link"],
            ["2026-03-18"],
        )
        SubmittedRound.objects.create(
            presentation_id="old-rhyming-round",
            title="Rhyming Picture Round",
            source_title="Rhyming Picture Round",
            creator="Alex",
            cooperative=True,
            link="https://docs.google.com/presentation/d/old-rhyming-round/edit",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Rhyming Picture Round")
        self.assertEqual(round_payload["source_title"], "Rhyming Picture Round")
        self.assertEqual(round_payload["creator"], "Megan")
        self.assertFalse(round_payload["coop"])
        self.assertEqual(round_payload["presentation_id"], "")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_does_not_overlay_coop_from_same_title_creator_on_different_date(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://mail.google.com/new-share-link"],
            ["Rhyming Picture Round"],
            ["Alex"],
            ["https://mail.google.com/new-share-link"],
            ["2026-03-18"],
        )
        SubmittedRound.objects.create(
            presentation_id="old-rhyming-round",
            title="Rhyming Picture Round",
            source_title="Rhyming Picture Round",
            creator="Alex",
            shared_date=datetime.date(2026, 3, 11),
            cooperative=True,
            link="https://mail.google.com/older-share-link",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Rhyming Picture Round")
        self.assertEqual(round_payload["creator"], "Alex")
        self.assertEqual(round_payload["shared_date"], "2026-03-18")
        self.assertFalse(round_payload["coop"])
        self.assertEqual(round_payload["presentation_id"], "")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_overlays_coop_for_exact_title_creator_date_match(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://mail.google.com/new-share-link"],
            ["Rhyming Picture Round"],
            ["Alex"],
            ["https://mail.google.com/new-share-link"],
            ["2026-03-18"],
        )
        SubmittedRound.objects.create(
            presentation_id="dated-rhyming-round",
            title="Rhyming Picture Round",
            source_title="Rhyming Picture Round",
            creator="Alex",
            shared_date=datetime.date(2026, 3, 18),
            cooperative=True,
            link="https://mail.google.com/older-share-link",
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Rhyming Picture Round")
        self.assertEqual(round_payload["creator"], "Alex")
        self.assertEqual(round_payload["shared_date"], "2026-03-18")
        self.assertTrue(round_payload["coop"])
        self.assertEqual(round_payload["presentation_id"], "dated-rhyming-round")

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_shows_unread_gmail_round_even_if_previously_consumed(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["Shared Deck Title"],
            ["hailsciencetrivia@gmail.com"],
            ["https://docs.google.com/presentation/d/swoop-123/edit"],
            ["2026-03-15"],
        )
        SubmittedRound.objects.create(
            presentation_id="swoop-123",
            title="Winged Science",
            creator="Alex",
            cooperative=True,
            link="https://docs.google.com/presentation/d/swoop-123/edit",
            is_consumed=True,
        )

        response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(response.status_code, 200)
        round_payload = response.json()["rounds"][0]
        self.assertEqual(round_payload["title"], "Winged Science")
        self.assertEqual(round_payload["source_title"], "Shared Deck Title")
        self.assertEqual(round_payload["creator"], "Alex")
        self.assertTrue(round_payload["is_new"])

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_uses_short_cache(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://example.com/new-round"],
            ["Fresh Round"],
            ["Ichigo"],
            ["https://example.com/source-round"],
            ["2026-03-14"],
        )

        first_response = self.client.get(reverse("collect_rounds_api"))
        second_response = self.client.get(reverse("collect_rounds_api"))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(mock_get_round_titles_and_links.call_count, 1)

    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_refresh_bypasses_cache(self, mock_get_round_titles_and_links):
        mock_get_round_titles_and_links.return_value = (
            ["https://example.com/new-round"],
            ["Fresh Round"],
            ["Ichigo"],
            ["https://example.com/source-round"],
            ["2026-03-14"],
        )

        first_response = self.client.get(reverse("collect_rounds_api"))
        refresh_response = self.client.get(reverse("collect_rounds_api"), {"refresh": "1"})

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(mock_get_round_titles_and_links.call_count, 2)

    @patch("GPTrivia.views.ensure_available_rounds_refresh_worker_running", return_value=True)
    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_collect_rounds_api_background_returns_cached_rounds_without_waiting_for_gmail(
        self,
        mock_get_round_titles_and_links,
        mock_ensure_refresh_worker,
    ):
        SubmittedRound.objects.create(
            presentation_id="cached-123",
            title="Cached New Round",
            source_title="Cached New Round",
            creator="Alex",
            shared_date=datetime.date(2026, 3, 20),
            cooperative=True,
            link="https://docs.google.com/presentation/d/cached-123/edit",
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
            link="https://example.com/historic-round",
        )

        response = self.client.get(reverse("collect_rounds_api"), {"background": "1"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["refreshing"])
        self.assertEqual([round_data["title"] for round_data in payload["rounds"]], ["Cached New Round", "Historic Round"])
        self.assertTrue(payload["rounds"][0]["is_new"])
        self.assertTrue(payload["rounds"][0]["coop"])
        mock_get_round_titles_and_links.assert_not_called()
        mock_ensure_refresh_worker.assert_called_once()

    @patch("GPTrivia.views._broadcast_home_available_rounds_refresh")
    @patch("GPTrivia.views.get_round_titles_and_links")
    def test_available_rounds_background_refresh_persists_email_rounds_and_broadcasts_sorted_payload(
        self,
        mock_get_round_titles_and_links,
        mock_broadcast,
    ):
        mock_get_round_titles_and_links.return_value = (
            [
                "https://docs.google.com/presentation/d/older-round/edit",
                "https://docs.google.com/presentation/d/newer-round/edit",
            ],
            ["Older Round", "Newer Round"],
            ["Alex", "Megan"],
            [
                "https://docs.google.com/presentation/d/older-round/edit",
                "https://docs.google.com/presentation/d/newer-round/edit",
            ],
            ["2026-03-14", "2026-03-21"],
        )

        data = views._refresh_available_rounds_from_email()

        self.assertIsNotNone(data)
        self.assertEqual(
            list(SubmittedRound.objects.order_by("shared_date").values_list("title", "is_consumed")),
            [("Older Round", False), ("Newer Round", False)],
        )
        self.assertEqual([round_data["title"] for round_data in data[:2]], ["Newer Round", "Older Round"])
        mock_broadcast.assert_called_once()
        broadcast_rounds = mock_broadcast.call_args.args[0]
        self.assertEqual([round_data["title"] for round_data in broadcast_rounds[:2]], ["Newer Round", "Older Round"])

    def test_save_available_round_metadata_uses_shared_date_in_persistence_for_linkless_rounds(self):
        first_response = self.client.post(
            reverse("save_available_round_metadata"),
            data={
                "title": "Winged Science",
                "source_title": "Winged Science",
                "creator": "Alex",
                "link": "",
                "old_link": "",
                "shared_date": "2026-03-15",
                "coop": True,
            },
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("save_available_round_metadata"),
            data={
                "title": "Winged Science",
                "source_title": "Winged Science",
                "creator": "Alex",
                "link": "",
                "old_link": "",
                "shared_date": "2026-03-22",
                "coop": False,
            },
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        saved_rounds = list(SubmittedRound.objects.filter(title="Winged Science", creator="Alex").order_by("shared_date"))
        self.assertEqual(len(saved_rounds), 2)
        self.assertEqual(
            [round_obj.shared_date.isoformat() if round_obj.shared_date else "" for round_obj in saved_rounds],
            ["2026-03-15", "2026-03-22"],
        )
        self.assertTrue(saved_rounds[0].cooperative)
        self.assertFalse(saved_rounds[1].cooperative)
        self.assertNotEqual(saved_rounds[0].presentation_id, saved_rounds[1].presentation_id)

    @patch(
        "GPTrivia.views.create_presentation",
        return_value=(
            "presentation-generated",
            ["Alex"],
            ["Historic Flags"],
            ["https://docs.google.com/presentation/d/presentation-generated/edit#slide=id.copied-round"],
        ),
    )
    @patch("GPTrivia.views.ensure_home_presentation_build_worker_running")
    def test_generate_accepts_historical_round_selection_and_stores_copied_link(self, _worker_mock, create_mock):
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
        job = HomePresentationBuildJob.objects.get()
        from GPTrivia.views import _run_home_presentation_build_job

        with patch("GPTrivia.views._broadcast_home_build_state"):
            with patch("GPTrivia.views._broadcast_home_presentation_refresh"):
                with patch("GPTrivia.views._broadcast_home_build_result"):
                    _run_home_presentation_build_job(job.id)
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
        self.assertEqual(
            stored_round.source_link,
            "https://docs.google.com/presentation/d/source-merged/edit#slide=id.round-start",
        )
