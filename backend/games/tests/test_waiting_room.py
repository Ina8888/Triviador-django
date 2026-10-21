from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from games.models import Game, Player, WaitingRoomEntry
from games.services import form_game, join_waiting_room, leave_waiting_room

User = get_user_model()


class WaitingRoomTests(TestCase):
    def setUp(self):
        self.users = []
        for i in range(1, 6):
            u = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@test.com",
                password="password123",)
            self.users.append(u)

    def test_form_game_with_five_players(self):
        #Test 1 - when 5 waiting players, 3 are chosen, 2 continue wainting
        for u in self.users:
            WaitingRoomEntry.objects.create(user=u)
        self.assertEqual(WaitingRoomEntry.objects.count(), 5)

        game = form_game()

        #New game is created with waiting status
        self.assertIsNotNone(game)
        self.assertEqual(game.status, Game.Status.WAITING)

        #exactly 3 players with different colors and 0 points
        players = game.players.all()
        self.assertEqual(players.count(), 3)
        colors = {p.color for p in players}

        self.assertEqual(colors, {"red", "green", "blue"})
        for p in players:
            self.assertEqual(p.score, 0)

        self.assertEqual(game.rounds.count(), 0)
        self.assertEqual(game.territories.count(), 0)
        self.assertEqual(WaitingRoomEntry.objects.count(), 2)

        #2 players left waiting and they are not in the game
        game_users = {p.user for p in players}
        waiting_users = {e.user for e in WaitingRoomEntry.objects.all()}
        self.assertTrue(game_users.isdisjoint(waiting_users))



    def test_form_game_with_two_players(self):
        #Test 2 - when 2 waiting players are waiting, no game is created
        WaitingRoomEntry.objects.create(user=self.users[0])
        WaitingRoomEntry.objects.create(user=self.users[1])

        result = form_game()
        self.assertIsNone(result)
        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(Player.objects.count(), 0)
        self.assertEqual(WaitingRoomEntry.objects.count(), 2)

    def test_api_endpoints(self):
        client = APIClient()
        client.force_authenticate(user=self.users[0])

        #join waiting room with API
        res = client.post("/api/games/waiting-room/join/")
        self.assertEqual(res.status_code, 201)

        #leave waiting room with API
        res = client.post("/api/games/waiting-room/leave/")
        self.assertEqual(res.status_code, 200)