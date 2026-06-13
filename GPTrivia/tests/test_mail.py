import base64
import datetime
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from GPTrivia.mail import (
    ROUND_SOURCE_MERGED_DECK,
    ROUND_SOURCE_WHOLE_PRESENTATION,
    _build_black_text_style_request,
    _build_update_summary_entries,
    _classify_round_source_link,
    _extract_slide_text,
    _extract_speaker_notes_text,
    _find_slide_index_for_round_title,
    _format_pacific_timestamp,
    _get_shape_text_content,
    _infer_historical_round_slide_range,
    _is_coop_at,
    _prepare_update_round_sources,
    _presentation_link_is_selected,
    _sanitize_slides_text,
    _utf16_code_units,
    _utf16_placeholder_range,
    convert_shared_presentation,
    find_shared_presentations,
    update_merged_presentation,
)


class MailHelpersTests(SimpleTestCase):
    def test_presentation_link_selection_ignores_url_suffix_differences(self):
        self.assertTrue(
            _presentation_link_is_selected(
                "https://docs.google.com/presentation/d/source-file-id/edit?usp=drive_web",
                ["https://docs.google.com/presentation/d/converted-file-id/edit"],
                ["https://docs.google.com/presentation/d/source-file-id/edit"],
            )
        )

    def test_presentation_link_selection_does_not_match_converted_id_alone(self):
        self.assertFalse(
            _presentation_link_is_selected(
                "https://docs.google.com/presentation/d/source-file-id/edit",
                ["https://docs.google.com/presentation/d/converted-file-id/edit"],
                [],
            )
        )

    @patch("GPTrivia.mail.convert_shared_presentation")
    @patch("GPTrivia.mail.build")
    def test_find_shared_presentations_marks_selected_message_from_repeated_sender(
        self,
        build_mock,
        convert_mock,
    ):
        gmail_service = Mock()
        messages_resource = gmail_service.users.return_value.messages.return_value
        messages_resource.list.return_value.execute.return_value = {
            "messages": [{"id": "message-1"}, {"id": "message-2"}],
        }

        message_urls = {
            "message-1": "https://docs.google.com/presentation/d/source-one/edit",
            "message-2": "https://docs.google.com/presentation/d/source-two/edit?usp=drive_web",
        }

        def get_message(*, userId, id, format, metadataHeaders=None):
            response = Mock()
            if format == "metadata":
                response.execute.return_value = {
                    "id": id,
                    "internalDate": "1" if id == "message-1" else "2",
                    "payload": {
                        "headers": [{"name": "From", "value": '"Megan <megan@example.com>'}],
                    },
                }
            else:
                encoded_body = base64.urlsafe_b64encode(message_urls[id].encode("utf-8")).decode("ascii")
                response.execute.return_value = {
                    "id": id,
                    "payload": {
                        "headers": [{"name": "From", "value": '"Megan <megan@example.com>'}],
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": encoded_body},
                            }
                        ],
                    },
                }
            return response

        messages_resource.get.side_effect = get_message
        messages_resource.modify.return_value.execute.return_value = {}
        build_mock.return_value = gmail_service
        convert_mock.side_effect = [
            "https://docs.google.com/presentation/d/converted-one/edit",
            "https://docs.google.com/presentation/d/converted-two/edit",
        ]

        find_shared_presentations(
            Mock(),
            processed_senders=[],
            selected_links=["https://docs.google.com/presentation/d/converted-two/edit"],
            old_links=[],
        )

        messages_resource.modify.assert_called_once_with(
            userId="me",
            id="message-2",
            body={"removeLabelIds": ["UNREAD"]},
        )

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

    @patch("GPTrivia.mail._create_temporary_round_copy", return_value="temp-round-copy")
    @patch("GPTrivia.mail._get_historical_round_context")
    def test_prepare_update_round_sources_snapshots_rounds_from_destination_presentation(
        self,
        historical_context_mock,
        create_temp_copy_mock,
    ):
        slides_service = Mock()
        slides_service.presentations.return_value.get.return_value.execute.return_value = {
            "slides": [
                {"objectId": "slide-0"},
                {"objectId": "slide-1"},
                {"objectId": "slide-2"},
            ]
        }
        drive_service = Mock()
        current_round = Mock()
        current_round.link = "https://docs.google.com/presentation/d/dest-presentation/edit#slide=id.slide-1"
        current_round.round_number = 1
        next_round = None
        historical_context_mock.return_value = (current_round, [current_round], next_round)

        prepared_links, temporary_ids = _prepare_update_round_sources(
            ["https://docs.google.com/presentation/d/dest-presentation/edit#slide=id.slide-1"],
            "dest-presentation",
            slides_service,
            drive_service,
        )

        create_temp_copy_mock.assert_called_once_with(
            drive_service,
            slides_service,
            "dest-presentation",
            1,
            1,
        )
        self.assertEqual(
            prepared_links,
            ["https://docs.google.com/presentation/d/temp-round-copy/edit"],
        )
        self.assertEqual(temporary_ids, ["temp-round-copy"])

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

    def test_extract_slide_text_reads_grouped_word_art_and_table_content(self):
        slide = {
            "pageElements": [
                {
                    "wordArt": {
                        "renderedText": "Animated Header",
                    }
                },
                {
                    "elementGroup": {
                        "children": [
                            {
                                "shape": {
                                    "text": {
                                        "textElements": [
                                            {"textRun": {"content": "Grouped answer 1"}},
                                        ]
                                    }
                                }
                            },
                            {
                                "table": {
                                    "tableRows": [
                                        {
                                            "tableCells": [
                                                {
                                                    "text": {
                                                        "textElements": [
                                                            {"textRun": {"content": "Table clue"}}
                                                        ]
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            },
                        ]
                    }
                },
            ]
        }

        extracted_text = _extract_slide_text(slide)

        self.assertIn("Animated Header", extracted_text)
        self.assertIn("Grouped answer 1", extracted_text)
        self.assertIn("Table clue", extracted_text)

    def test_extract_speaker_notes_text_reads_notes_body(self):
        slide = {
            "slideProperties": {
                "notesPage": {
                    "notesProperties": {
                        "speakerNotesObjectId": "speaker-notes-shape",
                    },
                    "pageElements": [
                        {
                            "objectId": "speaker-notes-shape",
                            "shape": {
                                "text": {
                                    "textElements": [
                                        {"textRun": {"content": "All answers visible here."}},
                                    ]
                                }
                            },
                        }
                    ],
                }
            }
        }

        self.assertEqual(_extract_speaker_notes_text(slide), "All answers visible here.")

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

    def test_is_coop_at_uses_placeholder_index_without_consuming_values(self):
        coop_values = ["", "on", ""]

        self.assertTrue(_is_coop_at(coop_values, 1))
        self.assertFalse(_is_coop_at(coop_values, 0))
        self.assertTrue(_is_coop_at(coop_values, 1))
        self.assertFalse(_is_coop_at(coop_values, 2))
        self.assertFalse(_is_coop_at(coop_values, 3))

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

    def test_build_black_text_style_request_sets_text_to_black(self):
        request = _build_black_text_style_request("shape-1", 4, "Round Title", font_size=20)

        self.assertEqual(request["updateTextStyle"]["objectId"], "shape-1")
        self.assertEqual(request["updateTextStyle"]["fields"], "foregroundColor,fontSize")
        self.assertEqual(
            request["updateTextStyle"]["style"]["foregroundColor"]["opaqueColor"]["rgbColor"],
            {"red": 0, "green": 0, "blue": 0},
        )
        self.assertEqual(
            request["updateTextStyle"]["style"]["fontSize"],
            {"magnitude": 20, "unit": "PT"},
        )

    @patch("GPTrivia.mail.os.path.exists", return_value=True)
    @patch("GPTrivia.mail.find_shared_presentations")
    @patch("GPTrivia.mail._copy_presentation_via_apps_script")
    @patch("GPTrivia.mail._copy_round_into_presentation", return_value="https://example.com/copied-round")
    @patch("GPTrivia.mail.build")
    @patch("GPTrivia.mail.pickle.load")
    @patch("GPTrivia.mail.pickle.dump")
    @patch("builtins.open")
    def test_update_merged_presentation_uses_pre_scan_round_count_for_summary_slots(
        self,
        _open_mock,
        _pickle_dump_mock,
        pickle_load_mock,
        build_mock,
        _copy_round_into_presentation_mock,
        _copy_presentation_via_apps_script_mock,
        find_shared_presentations_mock,
        _path_exists_mock,
    ):
        credentials = Mock()
        credentials.expired = False
        credentials.refresh_token = None
        credentials.valid = True
        pickle_load_mock.return_value = credentials

        summary_content = "ROUND1\nCREATOR1\nROUND2\nCREATOR2\nROUND3\nCREATOR3\nROUND4\nCREATOR4\nROUND5\nCREATOR5"
        summary_element = {
            "objectId": "summary-shape",
            "shape": {
                "text": {
                    "textElements": [
                        {"textRun": {"content": "\n"}},
                        {"textRun": {"content": summary_content}},
                    ]
                }
            },
        }
        presentation_state = {
            "slides": [
                {"objectId": "slide-1"},
                {"objectId": "slide-2", "pageElements": [summary_element]},
                {"objectId": "slide-3"},
            ]
        }

        def presentations_get_side_effect(*args, **kwargs):
            response = Mock()
            response.execute.return_value = presentation_state
            return response

        recorded_requests = []

        def batch_update_side_effect(*args, **kwargs):
            body = kwargs.get("body", {})
            recorded_requests.append(body.get("requests", []))
            response = Mock()
            response.execute.return_value = {}
            return response

        slides_service = Mock()
        slides_service.presentations.return_value.get.side_effect = presentations_get_side_effect
        slides_service.presentations.return_value.batchUpdate.side_effect = batch_update_side_effect

        drive_service = Mock()
        script_service = Mock()

        def build_side_effect(service_name, version, credentials=None):
            if service_name == "slides":
                return slides_service
            if service_name == "drive":
                return drive_service
            if service_name == "script":
                return script_service
            raise AssertionError(f"Unexpected service: {service_name}")

        build_mock.side_effect = build_side_effect

        def mutate_processed_senders(_credentials, processed_senders, _links, _old_links):
            processed_senders.extend(["Megan", "Jenny", "Debi"])
            return [], []

        find_shared_presentations_mock.side_effect = mutate_processed_senders

        update_merged_presentation(
            "presentation-123",
            ["Alex"],
            ["New Round"],
            ["Alex"],
            ["https://example.com/new-round"],
            ["https://example.com/new-round"],
            ["on"],
        )

        expected_round2_start_index, _ = _utf16_placeholder_range(summary_content, "ROUND2")
        round_insert_requests = [
            request["insertText"]
            for request_group in recorded_requests
            for request in request_group
            if request.get("insertText", {}).get("objectId") == "summary-shape"
            and request["insertText"]["text"] == "New Round"
        ]
        black_text_requests = [
            request["updateTextStyle"]
            for request_group in recorded_requests
            for request in request_group
            if request.get("updateTextStyle", {}).get("objectId") == "summary-shape"
            and request["updateTextStyle"]["style"].get("foregroundColor", {})
                .get("opaqueColor", {})
                .get("rgbColor") == {"red": 0, "green": 0, "blue": 0}
        ]

        self.assertEqual(len(round_insert_requests), 1)
        self.assertEqual(round_insert_requests[0]["insertionIndex"], expected_round2_start_index)
        self.assertTrue(black_text_requests)

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
