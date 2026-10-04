import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from . models import Room, Message, Membership


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

    
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        is_member = await self.check_membership()
        if not is_member:
            await self.close(code=4003)
            return


        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()



    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get('content', '').strip()
        if not content:
            return


        message = await self.save_message(content)


        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": {
                    "id": message.id,
                    "sender": self.user.username,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
            }
        )


    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def check_membership(self):
        return Membership.objects.filter(room_id=self.room_id, user=self.user).exists()

    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(id=self.room_id)
        return Message.objects.create(room=room, sender=self.user, content=content)
  