# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from collections import deque
import asyncio
import json
import math
import uuid


def _normalize_button_reaction_ms(value):
    try:
        normalized_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(normalized_value) or normalized_value < 0:
        return None
    return round(normalized_value, 2)


def _upsert_button_press(presses, *, username, sender_id, reaction_ms):
    normalized_time = _normalize_button_reaction_ms(reaction_ms)
    normalized_name = str(username or '').strip()
    normalized_sender_id = str(sender_id or '').strip()
    if normalized_time is None or not normalized_name or not normalized_sender_id:
        return list(presses or [])

    next_presses = [dict(press) for press in (presses or [])]
    existing_index = next(
        (index for index, press in enumerate(next_presses) if press.get('sender_id') == normalized_sender_id),
        None,
    )

    if existing_index is None:
        next_presses.append({
            'username': normalized_name,
            'sender_id': normalized_sender_id,
            'reaction_ms': normalized_time,
            'order': len(next_presses),
        })
    else:
        existing_press = next_presses[existing_index]
        if normalized_time >= float(existing_press.get('reaction_ms', normalized_time)):
            return sorted(
                next_presses,
                key=lambda press: (float(press.get('reaction_ms', 0.0)), int(press.get('order', 0))),
            )
        existing_press['username'] = normalized_name
        existing_press['reaction_ms'] = normalized_time

    return sorted(
        next_presses,
        key=lambda press: (float(press.get('reaction_ms', 0.0)), int(press.get('order', 0))),
    )


def _serialize_button_results(presses):
    ordered_presses = [
        {
            'username': str(press.get('username', '')).strip(),
            'sender_id': str(press.get('sender_id', '')).strip(),
            'reaction_ms': _normalize_button_reaction_ms(press.get('reaction_ms')),
            'order': int(press.get('order', 0)),
        }
        for press in (presses or [])
    ]
    ordered_presses = [
        press for press in ordered_presses
        if press['username'] and press['sender_id'] and press['reaction_ms'] is not None
    ]
    ordered_presses.sort(key=lambda press: (press['reaction_ms'], press['order']))

    if not ordered_presses:
        return {
            'winner': None,
            'standings': [],
        }

    winning_time = ordered_presses[0]['reaction_ms']
    standings = []
    for index, press in enumerate(ordered_presses):
        standings.append({
            'place': index + 1,
            'username': press['username'],
            'reaction_ms': press['reaction_ms'],
            'miss_ms': round(press['reaction_ms'] - winning_time, 2),
        })

    return {
        'winner': standings[0],
        'standings': standings,
    }

class ScoresheetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = 'scoresheet_updates'
        self.room_group_name = 'scoresheet_%s' % self.room_name

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)

        message_type = text_data_json.get('type')
        if message_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    # Receive message from room group
    async def scoresheet_message(self, event):
        message = event['message']
        is_answer_sheet_message = (
            message.get('action') == 'answer_sheet'
            or (
                message.get('action') == 'update'
                and message.get('event') == 'answer_sheet_submit_score'
            )
        )
        if is_answer_sheet_message:
            user = self.scope.get('user')
            target_user_ids = {
                str(user_id)
                for user_id in message.get('target_user_ids', [])
                if user_id is not None
            }
            if (
                not user
                or not getattr(user, 'is_authenticated', False)
                or str(user.id) not in target_user_ids
            ):
                return

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))


class HomePageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'home_build_updates'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        if text_data_json.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def home_build_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'build_state',
            'build_state': event['build_state'],
        }))

    async def home_presentation_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presentation_refresh',
            'presentation': event['presentation'],
            'action': event.get('action', ''),
            'refreshed_at': event.get('refreshed_at', ''),
        }))

    async def home_build_result_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'build_result',
            'result': event.get('result') or {},
        }))

    async def home_available_rounds_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'available_rounds_refresh',
            'rounds': event.get('rounds') or [],
            'refreshed_at': event.get('refreshed_at', ''),
        }))


class ButtonPressConsumer(AsyncWebsocketConsumer):
    reset_task = None
    button_presses = []
    processed_event_ids = deque(maxlen=256)

    @classmethod
    def _mark_event_processed(cls, event_id):
        normalized_event_id = str(event_id or '').strip()
        if not normalized_event_id:
            return False
        if normalized_event_id in cls.processed_event_ids:
            return False
        cls.processed_event_ids.append(normalized_event_id)
        return True

    @classmethod
    def _clear_button_results(cls):
        cls.button_presses = []

    @classmethod
    def _button_results_payload(cls):
        return _serialize_button_results(cls.button_presses)

    async def connect(self):
        self.room_group_name = 'button_group'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'button_state',
            **type(self)._button_results_payload(),
        }))


    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data['type'] == 'unlock':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'unlock_message',
                    'sender_id': data.get('sender_id'),
                    'event_id': data.get('event_id') or uuid.uuid4().hex,
                }
            )
        elif data['type'] == 'lock':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'lock_message',
                    'sender_id': data.get('sender_id'),
                    'event_id': data.get('event_id') or uuid.uuid4().hex,
                }
            )
        elif data['type'] == 'update':
            username = data['username']
            client_timestamp = data.get('timestamp_diff')

            # Cancel any existing reset task
            if type(self).reset_task and not type(self).reset_task.done():
                type(self).reset_task.cancel()

            # Create a new reset task
            type(self).reset_task = asyncio.create_task(self.schedule_reset())

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'update_message',
                    'username': username,
                    'sender_id': data.get('sender_id'),
                    'timestamp_diff': client_timestamp,
                    'event_id': data.get('event_id') or uuid.uuid4().hex,
                }
            )

        elif data['type'] == 'host_options_toggle':
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'host_options_toggle_message', 'sender_id': data.get('sender_id')}
            )

    async def schedule_reset(self):
        # This coroutine waits exactly 2 seconds.
        try:
            await asyncio.sleep(2)
            # After exactly 2 seconds with no new message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'reset_message'
                }
            )
        except asyncio.CancelledError:
            # This happens if a new message arrives before 2 seconds are up
            # Just pass and let the new timer take over
            pass
        finally:
            if type(self).reset_task is asyncio.current_task():
                type(self).reset_task = None

    # async def periodic_reset(self):
    #     while True:
    #         try:
    #             current_time = time.time()
    #             # Only send reset if no update message received in the last 2 seconds
    #             if current_time - type(self).last_update_time > 2:
    #                 print("Sending periodic reset message (no updates in last 2 seconds).")
    #                 await self.channel_layer.group_send(
    #                     self.room_group_name,
    #                     {
    #                         'type': 'reset_message'
    #                     }
    #                 )
    #             else:
    #                 print("Skipping periodic reset (recent update received).")
    #             await asyncio.sleep(2)  # Check every 2 seconds
    #         except asyncio.CancelledError:
    #             # Handle task cancellation
    #             print("Periodic reset task canceled.")
    #             break

    async def reset_message(self, event):
        # Send reset message to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'reset_max_time',
            **type(self)._button_results_payload(),
        }))

    async def lock_message(self, event):
        if type(self)._mark_event_processed(event.get('event_id')):
            type(self)._clear_button_results()
        await self.send(text_data=json.dumps({
            'type': 'lock',
            'sender_id': event.get('sender_id'),
            **type(self)._button_results_payload(),
        }))

    async def unlock_message(self, event):
        if type(self)._mark_event_processed(event.get('event_id')):
            type(self)._clear_button_results()
        await self.send(text_data=json.dumps({
            'type': 'unlock',
            'sender_id': event.get('sender_id'),
            **type(self)._button_results_payload(),
        }))

    async def update_message(self, event):
        if type(self)._mark_event_processed(event.get('event_id')):
            type(self).button_presses = _upsert_button_press(
                type(self).button_presses,
                username=event.get('username'),
                sender_id=event.get('sender_id'),
                reaction_ms=event.get('timestamp_diff'),
            )
        payload = type(self)._button_results_payload()
        await self.send(
            text_data=json.dumps({
                'type': 'update',
                'sender_id': event.get('sender_id'),
                **payload,
            }))

    async def host_options_toggle_message(self, event):
        await self.send(text_data=json.dumps({'type': 'host_options_toggle', 'sender_id': event.get('sender_id')}))
