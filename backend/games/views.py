from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .services import join_waiting_room, leave_waiting_room

#class for users to join the waiting room
class JoinWaitingRoomView(APIView):

    permission_classes = [IsAuthenticated]
    def post(self, request):
        success, result = join_waiting_room(request.user)
        if not success:
            return Response({"error": result}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "User written in waiting room"}, status=status.HTTP_201_CREATED)


class LeaveWaitingRoomView(APIView):

    permission_classes = [IsAuthenticated]
    def post(self, request):
        success = leave_waiting_room(request.user)
        if success:
            return Response({"message": "User left waiting room"})
        return Response({"message": "User was not in waiting room"})