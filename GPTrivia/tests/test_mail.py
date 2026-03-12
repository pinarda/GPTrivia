import datetime
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from GPTrivia.mail import (
    _format_pacific_timestamp,
    _sanitize_slides_text,
    _utf16_code_units,
    _utf16_placeholder_range,
    convert_shared_presentation,
)


class MailHelpersTests(SimpleTestCase):
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
