# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

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
        else:
            message = text_data_json['message']
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'scoresheet_message',
                    'message': message
                }
            )

    # Receive message from room group
    async def scoresheet_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))


class ButtonPressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = 'button_press_updates'
        self.room_group_name = f'button_press_{self.room_name}'

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

    async def receive(self, text_data):
        data = json.loads(text_data)
        username = data.get('username')

        # Broadcast the username to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'button_press_event',
                'username': username,
            }
        )

    async def button_press_event(self, event):
        username = event['username']

        # Send the updated username to the WebSocket
        await self.send(text_data=json.dumps({
            'username': username
        }))
