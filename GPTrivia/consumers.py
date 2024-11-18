# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import time

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
        self.room_group_name = 'button_group'

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

        if data['type'] == 'unlock':
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'unlock_message', 'sender_id': data.get('sender_id')}
            )
        elif data['type'] == 'lock':
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'lock_message', 'sender_id': data.get('sender_id')}
            )
        elif data['type'] == 'update':
            username = data['username']
            client_timestamp = data.get('timestamp')

            if client_timestamp:
                server_time = time.time() * 1000  # Current server time in milliseconds
                rtt = server_time - client_timestamp

                # Log and store the RTT
                self.connected_clients[self.client_id]["rtt"] = rtt
                print(f"RTT for client {self.client_id}: {rtt} ms")

            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'update_message', 'username': username, 'sender_id': data.get('sender_id')}
            )
        elif data['type'] == 'host_options_toggle':
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'host_options_toggle_message', 'sender_id': data.get('sender_id')}
            )

    async def lock_message(self, event):
        await self.send(text_data=json.dumps({'type': 'lock', 'sender_id': event.get('sender_id')}))

    async def unlock_message(self, event):
        await self.send(text_data=json.dumps({'type': 'unlock', 'sender_id': event.get('sender_id')}))

    async def update_message(self, event):
        username = event['username']
        await self.send(
            text_data=json.dumps({'type': 'update', 'username': username, 'sender_id': event.get('sender_id')}))

    async def host_options_toggle_message(self, event):
        await self.send(text_data=json.dumps({'type': 'host_options_toggle', 'sender_id': event.get('sender_id')}))
