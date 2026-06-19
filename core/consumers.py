import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MeetingNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'meeting_notifications'

        # Join room group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from room group
    async def meeting_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))
