# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import time
import asyncio

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
    # periodic_task = None  # Reference to the periodic task
    reset_task = None  # Reference to the reset task
    last_update_time = 0  # Class-level variable to track the last update time
    async def connect(self):
        self.room_group_name = 'button_group'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Start periodic task for resetting max_time
        # if not type(self).periodic_task:
        #     type(self).periodic_task = asyncio.create_task(self.periodic_reset())


    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Dynamically reference the class to manage periodic_task
        if not self.channel_layer.groups[self.room_group_name]:  # Check if group is empty
            if type(self).periodic_task:
                type(self).periodic_task.cancel()
                type(self).periodic_task = None

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
            client_timestamp = data.get('timestamp_diff')

            # if client_timestamp:
            #     server_time = time.time() * 1000  # Current server time in milliseconds
                # rtt = server_time - client_timestamp

                # Log and store the RTT
                # self.connected_clients[self.client_id]["rtt"] = rtt
                # print(f"RTT for client {self.client_id}: {rtt} ms")
            type(self).last_update_time = time.time()
            print(f"Update message received. Last update time set to {type(self).last_update_time}")


            self.last_update_time = time.time()

            # Cancel any existing reset task
            if self.reset_task and not self.reset_task.done():
                self.reset_task.cancel()

            # Create a new reset task
            self.reset_task = asyncio.create_task(self.schedule_reset())

            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'update_message', 'username': username, 'sender_id': data.get('sender_id'), 'timestamp_diff': client_timestamp}
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
            print("Sending exact 2-second reset message.")
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
            'type': 'reset_max_time'
        }))

    async def lock_message(self, event):
        await self.send(text_data=json.dumps({'type': 'lock', 'sender_id': event.get('sender_id')}))

    async def unlock_message(self, event):
        await self.send(text_data=json.dumps({'type': 'unlock', 'sender_id': event.get('sender_id')}))

    async def update_message(self, event):
        username = event['username']
        await self.send(
            text_data=json.dumps({'type': 'update', 'username': username, 'sender_id': event.get('sender_id'), 'timestamp': event.get('timestamp_diff')}))

    async def host_options_toggle_message(self, event):
        await self.send(text_data=json.dumps({'type': 'host_options_toggle', 'sender_id': event.get('sender_id')}))
