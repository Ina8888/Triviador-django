from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from games.models import Game, Player, Territory

User = get_user_model()


class TerritoryModelTests(TestCase):
    """Tests for Territory model, constraints, and relationships."""

    def setUp(self):
        self.game = Game.objects.create()
        self.user = User.objects.create_user(
            username="player1", email="p1@example.com", password="pw"
        )
        self.player = Player.objects.create(
            user=self.user, game=self.game, color=Player.Color.RED
        )

    def test_create_territory_defaults(self):
        """Territory has default score 0 and owner None."""
        t = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets"
        )
        self.assertEqual(t.score, 0)
        self.assertIsNone(t.owner)
        self.assertEqual(t.game, self.game)
        self.assertIn("sredets", str(t))

    def test_unique_name_per_game(self):
        """Duplicate territory name in the same game raises IntegrityError."""
        Territory.objects.create(game=self.game, name="Средец", slug="sredets-1")
        with self.assertRaises(IntegrityError):
            Territory.objects.create(game=self.game, name="Средец", slug="sredets-2")

    def test_unique_slug_per_game(self):
        """Duplicate territory slug in the same game raises IntegrityError."""
        Territory.objects.create(game=self.game, name="Средец 1", slug="sredets")
        with self.assertRaises(IntegrityError):
            Territory.objects.create(game=self.game, name="Средец 2", slug="sredets")

    def test_same_name_and_slug_allowed_in_different_games(self):
        """Different games can have territories with identical names and slugs."""
        game2 = Game.objects.create()
        t1 = Territory.objects.create(game=self.game, name="Средец", slug="sredets")
        t2 = Territory.objects.create(game=game2, name="Средец", slug="sredets")
        self.assertEqual(t1.name, t2.name)
        self.assertEqual(t1.slug, t2.slug)
        self.assertNotEqual(t1.game, t2.game)

    def test_negative_score_raises_integrity_error(self):
        """Score cannot be negative."""
        from django.db import transaction
        t = Territory(game=self.game, name="Средец", slug="sredets", score=-1)
        with self.assertRaises(ValidationError):
            t.full_clean()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                t.save()

    def test_owner_from_same_game_allowed(self):
        """Player from the same game can own the territory."""
        t = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", owner=self.player
        )
        t.full_clean()
        self.assertEqual(t.owner, self.player)

    def test_owner_from_different_game_rejected(self):
        """Player from another game cannot own this territory."""
        other_game = Game.objects.create()
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="pw"
        )
        other_player = Player.objects.create(
            user=other_user, game=other_game, color=Player.Color.BLUE
        )

        t = Territory(
            game=self.game, name="Средец", slug="sredets", owner=other_player
        )
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_territory_without_owner_is_valid(self):
        """Territories without owners are completely valid."""
        t = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", owner=None
        )
        t.full_clean()
        self.assertIsNone(t.owner)

    def test_cross_game_neighbors_rejected_by_clean(self):
        """Neighbor relationship cannot span across different games."""
        game2 = Game.objects.create()
        t1 = Territory.objects.create(game=self.game, name="Средец", slug="sredets")
        t2 = Territory.objects.create(game=game2, name="Дунавия", slug="dunaviya")

        t1.neighbors.add(t2)
        with self.assertRaises(ValidationError):
            t1.full_clean()

    def test_territory_cannot_be_own_neighbor(self):
        """Territory cannot be added as its own neighbor."""
        t = Territory.objects.create(game=self.game, name="Средец", slug="sredets")
        t.neighbors.add(t)
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_player_and_game_territories_relationships(self):
        """player.territories and game.territories properly resolve related objects."""
        t1 = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", owner=self.player
        )
        t2 = Territory.objects.create(
            game=self.game, name="Дунавия", slug="dunaviya", owner=self.player
        )
        t3 = Territory.objects.create(
            game=self.game, name="Скали", slug="skali", owner=None
        )

        self.assertEqual(set(self.game.territories.all()), {t1, t2, t3})
        self.assertEqual(set(self.player.territories.all()), {t1, t2})

    def test_game_isolation(self):
        """Modifications to territories in Game 1 do not affect Game 2."""
        game2 = Game.objects.create()
        t1 = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", score=100
        )
        t2 = Territory.objects.create(
            game=game2, name="Средец", slug="sredets", score=0
        )

        t1.score = 300
        t1.save()
        t2.refresh_from_db()

        self.assertEqual(t1.score, 300)
        self.assertEqual(t2.score, 0)

    def test_no_automatic_territory_creation_on_game_create(self):
        """Game creation in M04 does not automatically initialize territories (deferred to M05)."""
        new_game = Game.objects.create()
        self.assertEqual(new_game.territories.count(), 0)
        self.assertEqual(new_game.status, Game.Status.WAITING)
