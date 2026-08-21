import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from GPTrivia.consumers import ScoresheetConsumer


class ScoresheetConsumerTests(SimpleTestCase):
    def _consumer_for_user(self, user_id):
        consumer = ScoresheetConsumer()
        consumer.scope = {
            'user': SimpleNamespace(id=user_id, is_authenticated=True),
        }
        consumer.send = AsyncMock()
        return consumer

    def test_answer_sheet_message_is_not_sent_to_non_target_user(self):
        consumer = self._consumer_for_user(1)

        async_to_sync(consumer.scoresheet_message)({
            'message': {
                'action': 'answer_sheet',
                'event': 'answer_sheet_save',
                'target_user_ids': [2],
            },
        })

        consumer.send.assert_not_awaited()

    def test_answer_sheet_message_is_sent_to_target_user(self):
        consumer = self._consumer_for_user(1)
        message = {
            'action': 'answer_sheet',
            'event': 'answer_sheet_save',
            'target_user_ids': [1],
        }

        async_to_sync(consumer.scoresheet_message)({'message': message})

        consumer.send.assert_awaited_once_with(text_data=json.dumps({'message': message}))

    @patch('GPTrivia.consumers._get_answer_sheet_sync_payload', new_callable=AsyncMock)
    def test_authenticated_user_can_request_answer_sheet_state(self, get_sync_payload):
        get_sync_payload.return_value = {
            'current_user_id': 1,
            'selected_date': '2026-08-21',
            'rounds': [],
        }
        consumer = self._consumer_for_user(1)

        async_to_sync(consumer.receive)(json.dumps({
            'type': 'answer_sheet_sync',
            'request_id': 'request-1',
            'selected_date': '2026-08-21',
        }))

        get_sync_payload.assert_awaited_once_with(consumer.scope['user'], '2026-08-21')
        consumer.send.assert_awaited_once_with(text_data=json.dumps({
            'type': 'answer_sheet_sync',
            'request_id': 'request-1',
            'payload': get_sync_payload.return_value,
        }))

    @patch('GPTrivia.consumers._get_answer_sheet_sync_payload', new_callable=AsyncMock)
    def test_unauthenticated_user_cannot_request_answer_sheet_state(self, get_sync_payload):
        consumer = ScoresheetConsumer()
        consumer.scope = {
            'user': SimpleNamespace(id=None, is_authenticated=False),
        }
        consumer.send = AsyncMock()

        async_to_sync(consumer.receive)(json.dumps({
            'type': 'answer_sheet_sync',
            'request_id': 'request-2',
            'selected_date': '2026-08-21',
        }))

        get_sync_payload.assert_not_awaited()
        consumer.send.assert_awaited_once_with(text_data=json.dumps({
            'type': 'answer_sheet_sync_error',
            'request_id': 'request-2',
            'detail': 'Authentication is required.',
        }))
