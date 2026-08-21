import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
