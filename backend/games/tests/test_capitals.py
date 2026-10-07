from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from games.models import Capital, Game, Player, Territory

User = get_user_model()


class CapitalModelTests(TestCase):
    """Tests for Capital model, constraints, and player access."""

    def setUp(self):
        self.game = Game.objects.create()
        self.user1 = User.objects.create_user(
            username="cap_user1", email="cu1@example.com", password="pw"
        )
        self.user2 = User.objects.create_user(
            username="cap_user2", email="cu2@example.com", password="pw"
        )
        self.player1 = Player.objects.create(
            user=self.user1, game=self.game, color=Player.Color.RED
        )
        self.player2 = Player.objects.create(
            user=self.user2, game=self.game, color=Player.Color.BLUE
        )
        self.territory1 = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", owner=self.player1
        )
        self.territory2 = Territory.objects.create(
            game=self.game, name="Дунавия", slug="dunaviya", owner=self.player2
        )

    def test_create_valid_capital(self):
        """Capital created with valid player and matching territory owner."""
        cap = Capital.objects.create(
            territory=self.territory1, player=self.player1
        )
        cap.full_clean()
        self.assertEqual(cap.health, 3)
        self.assertEqual(cap.player, self.player1)
        self.assertEqual(cap.territory, self.territory1)
        self.assertIn("Средец", str(cap))

    def test_one_capital_per_player_constraint(self):
        """A player cannot have more than one capital."""
        Capital.objects.create(territory=self.territory1, player=self.player1)
        # Attempt to create another territory owned by player 1
        t3 = Territory.objects.create(
            game=self.game, name="Скали", slug="skali", owner=self.player1
        )
        with self.assertRaises(IntegrityError):
            Capital.objects.create(territory=t3, player=self.player1)

    def test_one_capital_per_territory_constraint(self):
        """A territory cannot host more than one capital."""
        Capital.objects.create(territory=self.territory1, player=self.player1)
        with self.assertRaises(IntegrityError):
            Capital.objects.create(territory=self.territory1, player=self.player2)

    def test_capital_health_bounds(self):
        """Health values between 0 and 3 are valid, out-of-range values raise errors."""
        cap = Capital.objects.create(
            territory=self.territory1, player=self.player1, health=3
        )
        for h in [0, 1, 2, 3]:
            cap.health = h
            cap.full_clean()
            cap.save()
            self.assertEqual(cap.health, h)

        # Negative health rejected by clean
        cap.health = -1
        with self.assertRaises(ValidationError):
            cap.full_clean()

        # Health > 3 rejected by clean
        cap.health = 4
        with self.assertRaises(ValidationError):
            cap.full_clean()

    def test_capital_health_db_check_constraints(self):
        """Database constraint enforces health between 0 and 3."""
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Capital.objects.create(
                    territory=self.territory1, player=self.player1, health=-1
                )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Capital.objects.create(
                    territory=self.territory1, player=self.player1, health=4
                )

    def test_capital_destroyed_health_zero_retains_record(self):
        """Health 0 represents a destroyed capital, but does not delete the record."""
        cap = Capital.objects.create(
            territory=self.territory1, player=self.player1, health=0
        )
        cap.full_clean()
        cap.refresh_from_db()
        self.assertEqual(cap.health, 0)
        self.assertTrue(Capital.objects.filter(pk=cap.pk).exists())

    def test_cross_game_capital_rejected(self):
        """Player and territory must belong to the same game."""
        game2 = Game.objects.create()
        user_other = User.objects.create_user(
            username="other_u", email="ou@example.com", password="pw"
        )
        player_other = Player.objects.create(
            user=user_other, game=game2, color=Player.Color.GREEN
        )

        cap = Capital(territory=self.territory1, player=player_other)
        with self.assertRaises(ValidationError):
            cap.full_clean()

    def test_capital_owner_mismatch_rejected(self):
        """Territory must be owned by the player who owns the capital."""
        # territory1 is owned by player1, but capital assigned to player2
        cap = Capital(territory=self.territory1, player=self.player2)
        with self.assertRaises(ValidationError):
            cap.full_clean()

        # Unowned territory cannot be a capital
        unowned_t = Territory.objects.create(
            game=self.game, name="Скали", slug="skali", owner=None
        )
        cap_unowned = Capital(territory=unowned_t, player=self.player1)
        with self.assertRaises(ValidationError):
            cap_unowned.full_clean()

    def test_player_get_capital_method(self):
        """player.get_capital() returns Capital if present, and None if missing."""
        self.assertIsNone(self.player1.get_capital())
        cap = Capital.objects.create(
            territory=self.territory1, player=self.player1
        )
        self.assertEqual(self.player1.get_capital(), cap)
