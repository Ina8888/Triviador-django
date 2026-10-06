from django.db import IntegrityError
from django.test import TestCase
from django.contrib.auth import get_user_model

from games.models import Game, Player

User = get_user_model()


class PlayerCreationTests(TestCase):
    """Tests for Player model creation and constraints."""

    def setUp(self):
        self.game = Game.objects.create()
        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")
        self.user3 = User.objects.create_user(username="user3", email="user3@example.com", password="testpass123")

    def test_add_three_players_with_different_colors(self):
        """Three different users can join a game with three different colors."""
        p1 = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        p2 = Player.objects.create(user=self.user2, game=self.game, color=Player.Color.GREEN)
        p3 = Player.objects.create(user=self.user3, game=self.game, color=Player.Color.BLUE)
        self.assertEqual(self.game.players.count(), 3)
        self.assertEqual(p1.score, 0)
        self.assertEqual(p2.score, 0)
        self.assertEqual(p3.score, 0)

    def test_player_default_score_is_zero(self):
        """A new player starts with score 0."""
        player = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        self.assertEqual(player.score, 0)

    def test_player_str(self):
        """String representation includes user, game, and color."""
        player = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        self.assertIn("red", str(player))

    def test_duplicate_user_in_same_game_raises_error(self):
        """The same user cannot join the same game twice."""
        Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        with self.assertRaises(IntegrityError):
            Player.objects.create(user=self.user1, game=self.game, color=Player.Color.GREEN)

    def test_duplicate_color_in_same_game_raises_error(self):
        """Two different users cannot have the same color in the same game."""
        Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        with self.assertRaises(IntegrityError):
            Player.objects.create(user=self.user2, game=self.game, color=Player.Color.RED)

    def test_same_user_can_join_different_games(self):
        """The same user can join different games."""
        game2 = Game.objects.create()
        Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        Player.objects.create(user=self.user1, game=game2, color=Player.Color.BLUE)
        self.assertEqual(Player.objects.filter(user=self.user1).count(), 2)

    def test_same_color_can_be_used_in_different_games(self):
        """The same color can be used in different games."""
        game2 = Game.objects.create()
        Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        Player.objects.create(user=self.user2, game=game2, color=Player.Color.RED)
        self.assertEqual(Player.objects.filter(color=Player.Color.RED).count(), 2)

    def test_negative_score_raises_error(self):
        """A player's score cannot be negative (CheckConstraint)."""
        player = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        player.score = -1
        with self.assertRaises(IntegrityError):
            player.save()

    def test_player_score_update(self):
        """A player's score can be updated to a positive value."""
        player = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        player.score = 150
        player.save()
        player.refresh_from_db()
        self.assertEqual(player.score, 150)

    def test_fourth_player_fails_validation(self):
        """Adding a 4th player to a game fails validation."""
        from django.core.exceptions import ValidationError
        Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        Player.objects.create(user=self.user2, game=self.game, color=Player.Color.GREEN)
        Player.objects.create(user=self.user3, game=self.game, color=Player.Color.BLUE)
        user4 = User.objects.create_user(username="user4", email="user4@example.com", password="testpass123")
        p4 = Player(user=user4, game=self.game, color=Player.Color.RED)
        with self.assertRaises(ValidationError):
            p4.full_clean()
