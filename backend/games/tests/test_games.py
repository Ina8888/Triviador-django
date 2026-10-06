from django.test import TestCase
from django.contrib.auth import get_user_model

from games.models import Game

User = get_user_model()


class GameCreationTests(TestCase):
    """Tests for Game model creation and lifecycle."""

    def test_game_created_with_waiting_status(self):
        """A new game starts with status 'waiting'."""
        game = Game.objects.create()
        self.assertEqual(game.status, Game.Status.WAITING)

    def test_game_has_created_at(self):
        """A new game has a recorded created_at timestamp."""
        game = Game.objects.create()
        self.assertIsNotNone(game.created_at)

    def test_game_str(self):
        """String representation includes pk and status."""
        game = Game.objects.create()
        self.assertIn("waiting", str(game))

    def test_is_active_false_for_waiting_game(self):
        """is_active() returns False for a waiting game."""
        game = Game.objects.create()
        self.assertFalse(game.is_active())

    def test_is_active_true_for_active_game(self):
        """is_active() returns True for an active game."""
        game = Game.objects.create(status=Game.Status.ACTIVE)
        self.assertTrue(game.is_active())

    def test_is_completed_false_for_active_game(self):
        """is_completed() returns False for an active game."""
        game = Game.objects.create(status=Game.Status.ACTIVE)
        self.assertFalse(game.is_completed())

    def test_is_completed_true_for_completed_game(self):
        """is_completed() returns True for a completed game."""
        game = Game.objects.create(status=Game.Status.COMPLETED)
        self.assertTrue(game.is_completed())

    def test_game_status_transition_waiting_to_active(self):
        """Game status can transition from waiting to active."""
        game = Game.objects.create()
        game.status = Game.Status.ACTIVE
        game.save()
        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.ACTIVE)

    def test_game_status_transition_active_to_completed(self):
        """Game status can transition from active to completed."""
        game = Game.objects.create(status=Game.Status.ACTIVE)
        game.status = Game.Status.COMPLETED
        game.save()
        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.COMPLETED)

    def test_get_current_round_returns_none_for_no_rounds(self):
        """get_current_round() returns None when there are no rounds."""
        game = Game.objects.create()
        self.assertIsNone(game.get_current_round())

    def test_start_game_with_three_players(self):
        """Game can be started when exactly 3 players have joined."""
        from games.models import Player
        game = Game.objects.create()
        u1 = User.objects.create_user(username="g_user1", email="g_user1@example.com", password="pw")
        u2 = User.objects.create_user(username="g_user2", email="g_user2@example.com", password="pw")
        u3 = User.objects.create_user(username="g_user3", email="g_user3@example.com", password="pw")
        Player.objects.create(user=u1, game=game, color=Player.Color.RED)
        Player.objects.create(user=u2, game=game, color=Player.Color.GREEN)
        Player.objects.create(user=u3, game=game, color=Player.Color.BLUE)
        game.start()
        self.assertEqual(game.status, Game.Status.ACTIVE)
        self.assertTrue(game.is_active())

    def test_start_game_with_less_than_three_players_fails(self):
        """Game cannot be started with fewer than 3 players."""
        from django.core.exceptions import ValidationError
        game = Game.objects.create()
        with self.assertRaises(ValidationError):
            game.start()

    def test_complete_game(self):
        """Game can be completed."""
        game = Game.objects.create(status=Game.Status.ACTIVE)
        game.complete()
        self.assertEqual(game.status, Game.Status.COMPLETED)
        self.assertTrue(game.is_completed())
