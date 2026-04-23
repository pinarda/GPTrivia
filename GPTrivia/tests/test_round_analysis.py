import io
import zipfile
import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from GPTrivia.models import GPTriviaRound, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun
from GPTrivia.round_analysis import (
    _apply_apps_script_media_links,
    _analyze_round_slides,
    _classify_round_structure,
    _extract_picture_grid_questions_by_layout,
    _extract_embedded_slide_media_assets,
    _extract_slide_media_items,
    _is_placeholder_media_url,
    _normalize_analysis_categories,
    _optimize_analysis_image_content,
    _store_round_analysis,
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
            reverse("trigger_round_analysis", args=[round_obj.id]),
        )
