from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Room, Membership, Message
from .serializers import AddMemberSerializer, RoomSerializer, MembershipSerializer, MessageSerializer
from .permissions import IsRoomMember

User = get_user_model()


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        room = serializer.save(created_by=self.request.user)
        Membership.objects.create(user=self.request.user, room=room) # creator auto-joins the room

    def get_queryset(self):
        # users only see rooms they are members of
        return Room.objects.filter(memberships__user=self.request.user).distinct()

    @action(detail=True, methods=["post"], serializer_class=AddMemberSerializer)
    def add_member(self, request, pk=None):
        room = self.get_object()
        if room.created_by != request.user:
            return Response({"detail": "Only the room creator can add members."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        membership, created = Membership.objects.get_or_create(user=user, room=room)
        if not created:
            return Response({"detail": "User is already a member of this room."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Messages history -- read-only over REST; creation happens via WebSocket."""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsRoomMember]

    def get_queryset(self):
        return Message.objects.filter(room_id=self.kwargs['room_pk'])

