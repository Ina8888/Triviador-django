from django.urls import path
from .views import JoinWaitingRoomView, LeaveWaitingRoomView

app_name = "games"
urlpatterns = [
    path("waiting-room/join/", JoinWaitingRoomView.as_view(), name="waiting_room_join"),
    path("waiting-room/leave/", LeaveWaitingRoomView.as_view(), name="waiting_room_leave"),
]