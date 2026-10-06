from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from games.models import Game, Player, Round

User = get_user_model()


class RoundCreationTests(TestCase):
    """Tests for Round model creation and lifecycle."""

    def setUp(self):
        self.game = Game.objects.create(status=Game.Status.ACTIVE)
        self.user1 = User.objects.create_user(username="round_user1", email="round_user1@example.com", password="testpass123")
        self.user2 = User.objects.create_user(username="round_user2", email="round_user2@example.com", password="testpass123")
        self.user3 = User.objects.create_user(username="round_user3", email="round_user3@example.com", password="testpass123")
        self.player1 = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        self.player2 = Player.objects.create(user=self.user2, game=self.game, color=Player.Color.GREEN)
        self.player3 = Player.objects.create(user=self.user3, game=self.game, color=Player.Color.BLUE)

    def test_round_created_with_pending_status(self):
        """A new round starts with status 'pending'."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        self.assertEqual(r.status, Round.Status.PENDING)

    def test_round_has_created_at(self):
        """A new round has a recorded created_at timestamp."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        self.assertIsNotNone(r.created_at)

    def test_round_no_winner_initially(self):
        """A new round has no winner."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE)
        self.assertIsNone(r.winner)

    def test_round_no_completed_at_initially(self):
        """A new round has no completed_at."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE)
        self.assertIsNone(r.completed_at)

    def test_round_str(self):
        """String representation includes number, game, and status."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        self.assertIn("Round 1", str(r))

    def test_round_types(self):
        """All four round types can be created."""
        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        Round.objects.create(game=self.game, number=2, type=Round.Type.BATTLE)
        Round.objects.create(game=self.game, number=3, type=Round.Type.CAPITAL_ATTACK)
        Round.objects.create(game=self.game, number=4, type=Round.Type.BONUS)
        self.assertEqual(self.game.rounds.count(), 4)

    def test_duplicate_round_number_in_same_game_raises_error(self):
        """Two rounds cannot have the same number in the same game."""
        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        with self.assertRaises(IntegrityError):
            Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE)

    def test_same_round_number_in_different_games(self):
        """The same round number can be used in different games."""
        game2 = Game.objects.create(status=Game.Status.ACTIVE)
        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        Round.objects.create(game=game2, number=1, type=Round.Type.CITY_CAPTURE)
        self.assertEqual(Round.objects.filter(number=1).count(), 2)

    def test_complete_round_with_winner(self):
        """A round can be completed with a winner from the same game."""
        r = Round.objects.create(
            game=self.game, number=1, type=Round.Type.CITY_CAPTURE, status=Round.Status.ACTIVE,
        )
        r.winner = self.player1
        r.status = Round.Status.COMPLETED
        r.completed_at = timezone.now()
        r.full_clean()
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        self.assertIsNotNone(r.completed_at)

    def test_winner_from_different_game_fails_validation(self):
        """A player from a different game cannot be the winner."""
        other_game = Game.objects.create()
        other_user = User.objects.create_user(username="other_user", email="other_user@example.com", password="testpass123")
        other_player = Player.objects.create(user=other_user, game=other_game, color=Player.Color.RED)

        r = Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE)
        r.winner = other_player
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_get_current_round_returns_highest_number(self):
        """get_current_round() returns the round with the highest number."""
        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        Round.objects.create(game=self.game, number=2, type=Round.Type.BATTLE)
        r3 = Round.objects.create(game=self.game, number=3, type=Round.Type.CAPITAL_ATTACK)
        current = self.game.get_current_round()
        self.assertEqual(current.pk, r3.pk)
        self.assertEqual(current.number, 3)

    def test_round_status_lifecycle(self):
        """A round transitions through pending -> active -> completed."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        self.assertEqual(r.status, Round.Status.PENDING)

        r.status = Round.Status.ACTIVE
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.status, Round.Status.ACTIVE)

        r.status = Round.Status.COMPLETED
        r.winner = self.player2
        r.completed_at = timezone.now()
        r.full_clean()
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertIsNotNone(r.completed_at)
        self.assertEqual(r.winner, self.player2)

    def test_round_complete_helper(self):
        """Round.complete(winner) completes the round with winner and timestamp."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE, status=Round.Status.ACTIVE)
        r.complete(winner=self.player1)
        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        self.assertIsNotNone(r.completed_at)

    def test_completed_round_without_completed_at_fails_validation(self):
        """A completed round without completed_at fails validation."""
        r = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        r.status = Round.Status.COMPLETED
        r.winner = self.player1
        with self.assertRaises(ValidationError):
            r.full_clean()
