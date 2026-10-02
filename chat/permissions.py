from rest_framework import permissions
from . models import Membership


class IsRoomMember(permissions.BasePermission):
    """
    Only allow members of a room to access it.
    """

    def has_object_permission(self, request, view):
        room_id = view.kwargs.get('room_pk') or request.data.get('room')
        if not room_id:
            return True # let object-level check handle it, or it's a room-less action
        return Membership.objects.filter(user=request.user, room_id=room_id).exists()