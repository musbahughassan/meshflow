from rest_framework import serializers
from . models import Room, Membership, Message


class RoomSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = Room
        fields = ['id', 'name', 'created_by', 'created_at']

class AddMemberSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)

class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Membership
        fields = ['id', 'username', 'room', 'joined_at']
        read_only_fields = ['joined_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')

    class Meta:
        model = Message
        fields = ['id', 'sender', 'room', 'content', 'created_at']
        read_only_fields = ['created_at', 'sender']

