import datetime
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from GPTrivia.mail import (
    ROUND_SOURCE_MERGED_DECK,
    ROUND_SOURCE_WHOLE_PRESENTATION,
    _build_update_summary_entries,
    _classify_round_source_link,
    _find_slide_index_for_round_title,
    _format_pacific_timestamp,
    _get_shape_text_content,
    _infer_historical_round_slide_range,
    _pop_is_coop,
    _sanitize_slides_text,
    _utf16_code_units,
    _utf16_placeholder_range,
    convert_shared_presentation,
)


class MailHelpersTests(SimpleTestCase):
    def test_classify_round_source_link_detects_whole_presentations(self):
        link_info = _classify_round_source_link(
            "https://docs.google.com/presentation/d/source-presentation-id/edit"
        )

        self.assertEqual(link_info["source_type"], ROUND_SOURCE_WHOLE_PRESENTATION)
        self.assertEqual(link_info["presentation_id"], "source-presentation-id")
        self.assertIsNone(link_info["slide_id"])

    def test_classify_round_source_link_detects_merged_deck_round_starts(self):
        link_info = _classify_round_source_link(
            "https://docs.google.com/presentation/d/source-presentation-id/edit#slide=id.g2f6f1"
        )

        self.assertEqual(link_info["source_type"], ROUND_SOURCE_MERGED_DECK)
        self.assertEqual(link_info["presentation_id"], "source-presentation-id")
        self.assertEqual(link_info["slide_id"], "g2f6f1")

    def test_classify_round_source_link_detects_embed_slide_links(self):
        link_info = _classify_round_source_link(
            "https://docs.google.com/presentation/d/source-presentation-id/embed?start=false#slide=id.g2f6f1"
        )

        self.assertEqual(link_info["source_type"], ROUND_SOURCE_MERGED_DECK)
        self.assertEqual(link_info["presentation_id"], "source-presentation-id")
        self.assertEqual(link_info["slide_id"], "g2f6f1")

    def test_classify_round_source_link_detects_embed_query_slide_links(self):
        link_info = _classify_round_source_link(
            "https://docs.google.com/presentation/d/source-presentation-id/embed?start=false&slide=id.g2f6f1"
        )

        self.assertEqual(link_info["source_type"], ROUND_SOURCE_MERGED_DECK)
        self.assertEqual(link_info["presentation_id"], "source-presentation-id")
        self.assertEqual(link_info["slide_id"], "g2f6f1")

    def test_utf16_placeholder_range_counts_emoji_as_two_code_units(self):
        content = "🚀 ROUND1 CREATOR1"

        start_index, end_index = _utf16_placeholder_range(content, "ROUND1")

        self.assertEqual(start_index, 3)
        self.assertEqual(end_index, 9)

    def test_sanitize_slides_text_keeps_emoji_and_removes_control_chars(self):
        self.assertEqual(_sanitize_slides_text("Round 🚀\x01"), "Round 🚀")
        self.assertEqual(_utf16_code_units("🚀"), 2)

    def test_format_pacific_timestamp_uses_pacific_timezone(self):
        utc_dt = datetime.datetime(2026, 6, 6, 1, 30, tzinfo=datetime.timezone.utc)

        self.assertEqual(
            _format_pacific_timestamp(int(utc_dt.timestamp() * 1000)),
            "June 05, 2026",
        )

    def test_infer_historical_round_slide_range_stops_before_next_round_start(self):
        slides = [
            {"objectId": "slide-0"},
            {"objectId": "slide-1"},
            {"objectId": "slide-2"},
            {"objectId": "slide-3"},
            {"objectId": "slide-4"},
            {"objectId": "slide-5"},
        ]

        start_index, end_index = _infer_historical_round_slide_range(
            slides,
            "slide-2",
            [
                "https://docs.google.com/presentation/d/source/edit#slide=id.slide-2",
                "https://docs.google.com/presentation/d/source/edit#slide=id.slide-4",
            ],
        )

        self.assertEqual((start_index, end_index), (2, 3))

    def test_infer_historical_round_slide_range_excludes_outro_for_last_round(self):
        slides = [
            {"objectId": "slide-0"},
            {"objectId": "slide-1"},
            {"objectId": "slide-2"},
            {"objectId": "slide-3"},
            {"objectId": "slide-4"},
            {"objectId": "slide-5"},
        ]

        start_index, end_index = _infer_historical_round_slide_range(
            slides,
            "slide-4",
            [
                "https://docs.google.com/presentation/d/source/edit#slide=id.slide-2",
                "https://docs.google.com/presentation/d/source/edit#slide=id.slide-4",
            ],
        )

        self.assertEqual((start_index, end_index), (4, 4))

    def test_find_slide_index_for_round_title_matches_slide_text(self):
        slides = [
            {
                "objectId": "slide-0",
                "pageElements": [],
            },
            {
                "objectId": "slide-1",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Flags Picture Round"}}
                                ]
                            }
                        }
                    }
                ],
            },
        ]

        self.assertEqual(
            _find_slide_index_for_round_title(slides, "Flags Picture Round"),
            1,
        )

    def test_get_shape_text_content_skips_slides_without_page_elements(self):
        presentation = {
            "slides": [
                {"objectId": "slide-0"},
                {
                    "objectId": "slide-1",
                    "pageElements": [
                        {
                            "objectId": "shape-1",
                            "shape": {
                                "text": {
                                    "textElements": [
                                        {"textRun": {"content": "Current "}},
                                        {"textRun": {"content": "Round"}},
                                    ]
                                }
                            },
                        }
                    ],
                },
            ]
        }

        self.assertEqual(
            _get_shape_text_content(presentation, "shape-1"),
            "Current Round",
        )

    def test_pop_is_coop_consumes_values_sequentially(self):
        coop_values = ["on", "", "on"]

        self.assertTrue(_pop_is_coop(coop_values))
        self.assertFalse(_pop_is_coop(coop_values))
        self.assertTrue(_pop_is_coop(coop_values))
        self.assertFalse(_pop_is_coop(coop_values))

    def test_build_update_summary_entries_starts_after_existing_rounds(self):
        entries = _build_update_summary_entries(
            1,
            ["New Round"],
            ["Alex"],
            ["on"],
        )

        self.assertEqual(
            entries,
            [
                {
                    "round_placeholder": "ROUND2",
                    "creator_placeholder": "CREATOR2",
                    "title": "New Round",
                    "creator_key": "Alex",
                    "coop": True,
                    "round_done": False,
                    "creator_done": False,
                }
            ],
        )

    def test_infer_historical_round_slide_range_uses_next_round_title_when_links_are_missing(self):
        slides = [
            {
                "objectId": "slide-0",
                "pageElements": [],
            },
            {
                "objectId": "slide-1",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Current Round"}}
                                ]
                            }
                        }
                    }
                ],
            },
            {
                "objectId": "slide-2",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Question slide"}}
                                ]
                            }
                        }
                    }
                ],
            },
            {
                "objectId": "slide-3",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Next Round"}}
                                ]
                            }
                        }
                    }
                ],
            },
            {
                "objectId": "slide-4",
                "pageElements": [],
            },
        ]

        start_index, end_index = _infer_historical_round_slide_range(
            slides,
            "slide-1",
            [
                "https://docs.google.com/presentation/d/source/edit#slide=id.slide-1",
            ],
            next_round_title="Next Round",
        )

        self.assertEqual((start_index, end_index), (1, 2))


class ConvertSharedPresentationTests(SimpleTestCase):
    @patch("GPTrivia.mail.build")
    def test_convert_shared_presentation_reuses_existing_google_slides_copy(self, build_mock):
        drive_service = Mock()
        build_mock.return_value = drive_service
        files_resource = drive_service.files.return_value
        files_resource.get.return_value.execute.return_value = {
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        files_resource.list.return_value.execute.return_value = {
            "files": [{"id": "existing-slides-copy"}],
        }

        converted_url = convert_shared_presentation(
            "https://docs.google.com/presentation/d/source-file-id/edit",
            credentials=Mock(),
        )

        self.assertEqual(
            converted_url,
            "https://docs.google.com/presentation/d/existing-slides-copy/edit",
        )
        files_resource.copy.assert_not_called()
        files_resource.update.assert_not_called()

    @patch("GPTrivia.mail.build")
    def test_convert_shared_presentation_tags_new_conversion_with_source_file_id(self, build_mock):
        drive_service = Mock()
        build_mock.return_value = drive_service
        files_resource = drive_service.files.return_value
        files_resource.get.return_value.execute.return_value = {
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        files_resource.list.return_value.execute.return_value = {"files": []}
        files_resource.copy.return_value.execute.return_value = {"id": "new-slides-copy"}
        files_resource.update.return_value.execute.return_value = {}

        converted_url = convert_shared_presentation(
            "https://docs.google.com/presentation/d/source-file-id/edit",
            credentials=Mock(),
        )

        self.assertEqual(
            converted_url,
            "https://docs.google.com/presentation/d/new-slides-copy/edit",
        )
        files_resource.copy.assert_called_once_with(
            fileId="source-file-id",
            body={"mimeType": "application/vnd.google-apps.presentation"},
        )
        files_resource.update.assert_called_once_with(
            fileId="new-slides-copy",
            body={"appProperties": {"converted_from_file_id": "source-file-id"}},
        )
