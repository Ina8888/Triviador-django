import random
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from games.map import MAP_DEFINITION, validate_game_territories
from games.models import Capital, Game, Player, Territory
from games.services import get_valid_capital_triplets, initialize_game

User = get_user_model()


class GameInitializationTests(TestCase):
    """Comprehensive test suite for M05 - Game Initialization."""

    def setUp(self):
        self.game = Game.objects.create(status=Game.Status.WAITING)
        self.u1 = User.objects.create_user(
            username="init_user1", email="iu1@example.com", password="pw"
        )
        self.u2 = User.objects.create_user(
            username="init_user2", email="iu2@example.com", password="pw"
        )
        self.u3 = User.objects.create_user(
            username="init_user3", email="iu3@example.com", password="pw"
        )
        self.p1 = Player.objects.create(
            user=self.u1, game=self.game, color=Player.Color.RED, score=0
        )
        self.p2 = Player.objects.create(
            user=self.u2, game=self.game, color=Player.Color.GREEN, score=0
        )
        self.p3 = Player.objects.create(
            user=self.u3, game=self.game, color=Player.Color.BLUE, score=0
        )

    def test_successful_game_initialization(self):
        """Waiting game with 3 players gets complete initial state and becomes active."""
        initialize_game(self.game)

        # 1. Status is active
        self.assertEqual(self.game.status, Game.Status.ACTIVE)
        self.assertTrue(self.game.is_active())

        # 2. Exactly 18 territories matching project map
        self.assertEqual(self.game.territories.count(), 18)
        self.assertTrue(validate_game_territories(self.game))

        # 3. Territory scores are 0
        for t in self.game.territories.all():
            self.assertEqual(t.score, 0)

        # 4. Player scores unchanged
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.p3.refresh_from_db()
        self.assertEqual(self.p1.score, 0)
        self.assertEqual(self.p2.score, 0)
        self.assertEqual(self.p3.score, 0)

        # 5. Exactly 3 capitals, each with health 3
        capitals = Capital.objects.filter(territory__game=self.game)
        self.assertEqual(capitals.count(), 3)
        for cap in capitals:
            self.assertEqual(cap.health, 3)

        # Each player has exactly one capital
        self.assertIsNotNone(self.p1.get_capital())
        self.assertIsNotNone(self.p2.get_capital())
        self.assertIsNotNone(self.p3.get_capital())

        # 6. Capital territories are mutually non-adjacent
        cap_territories = [cap.territory for cap in capitals]
        for i in range(len(cap_territories)):
            for j in range(i + 1, len(cap_territories)):
                t_a = cap_territories[i]
                t_b = cap_territories[j]
                self.assertNotIn(
                    t_b,
                    t_a.neighbors.all(),
                    f"Capitals {t_a.slug} and {t_b.slug} must not be adjacent!",
                )

        # 7. Ownership: 3 capital territories owned by respective players, remaining 15 neutral
        owned_territories = self.game.territories.filter(owner__isnull=False)
        self.assertEqual(owned_territories.count(), 3)
        for cap in capitals:
            self.assertEqual(cap.territory.owner, cap.player)

        unowned_territories = self.game.territories.filter(owner__isnull=True)
        self.assertEqual(unowned_territories.count(), 15)

        # 8. No rounds created
        self.assertEqual(self.game.rounds.count(), 0)

    def test_model_method_initialize(self):
        """Game.initialize() helper method performs initialization identically."""
        self.game.initialize()
        self.assertEqual(self.game.status, Game.Status.ACTIVE)
        self.assertEqual(self.game.territories.count(), 18)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 3)

    def test_initialization_fails_if_not_waiting(self):
        """Games in active or completed status cannot be initialized."""
        # Active
        active_game = Game.objects.create(status=Game.Status.ACTIVE)
        with self.assertRaises(ValidationError):
            initialize_game(active_game)

        # Completed
        completed_game = Game.objects.create(status=Game.Status.COMPLETED)
        with self.assertRaises(ValidationError):
            initialize_game(completed_game)

    def test_initialization_fails_if_player_count_not_three(self):
        """Cannot initialize games with fewer or more than 3 players."""
        # 0 players
        empty_game = Game.objects.create(status=Game.Status.WAITING)
        with self.assertRaises(ValidationError):
            initialize_game(empty_game)

        # 2 players
        two_player_game = Game.objects.create(status=Game.Status.WAITING)
        Player.objects.create(user=self.u1, game=two_player_game, color=Player.Color.RED)
        Player.objects.create(user=self.u2, game=two_player_game, color=Player.Color.GREEN)
        with self.assertRaises(ValidationError):
            initialize_game(two_player_game)

    def test_initialization_fails_if_already_has_territories(self):
        """Partial or pre-existing territories prevent initialization without auto-repair."""
        # Pre-create 1 territory in waiting game
        t = Territory.objects.create(game=self.game, name="Скали", slug="skali")
        with self.assertRaises(ValidationError):
            initialize_game(self.game)

        # Ensure state remained unchanged: status still waiting, still 1 territory
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.WAITING)
        self.assertEqual(self.game.territories.count(), 1)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 0)

    def test_repeat_initialization_fails(self):
        """Calling initialize_game a second time on an active game is cleanly rejected."""
        initialize_game(self.game)
        self.assertEqual(self.game.status, Game.Status.ACTIVE)

        with self.assertRaises(ValidationError):
            initialize_game(self.game)

        # Confirm territory count and capital count are unchanged (not doubled)
        self.assertEqual(self.game.territories.count(), 18)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 3)

    def test_initialization_fails_with_invalid_map_definition(self):
        """An invalid map graph definition causes rejection before any changes."""
        invalid_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": ["t0"]} for i in range(10)
        ]
        with self.assertRaises(ValidationError):
            initialize_game(self.game, map_definition=invalid_map)

        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.WAITING)
        self.assertEqual(self.game.territories.count(), 0)

    def test_initialization_fails_if_no_independent_capital_triplets(self):
        """Map with no independent triplet of size 3 fails without modifying game."""
        # Complete graph of 9 nodes (all nodes connected to all other nodes)
        k9_map = [
            {
                "slug": f"t{i}",
                "name": f"T{i}",
                "neighbors": [f"t{j}" for j in range(9) if j != i],
            }
            for i in range(9)
        ]
        with self.assertRaises(ValidationError):
            initialize_game(self.game, map_definition=k9_map)

        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.WAITING)
        self.assertEqual(self.game.territories.count(), 0)

    def test_deterministic_randomness_with_injected_rng(self):
        """Passing a seeded RNG yields deterministic, reproducible capital assignment."""
        rng1 = random.Random(42)
        initialize_game(self.game, random_generator=rng1)

        cap_slugs = sorted(
            [cap.territory.slug for cap in Capital.objects.filter(territory__game=self.game)]
        )

        # Reproduce with another game using the exact same seed
        game2 = Game.objects.create(status=Game.Status.WAITING)
        p2_1 = Player.objects.create(user=self.u1, game=game2, color=Player.Color.RED)
        p2_2 = Player.objects.create(user=self.u2, game=game2, color=Player.Color.GREEN)
        p2_3 = Player.objects.create(user=self.u3, game=game2, color=Player.Color.BLUE)

        rng2 = random.Random(42)
        initialize_game(game2, random_generator=rng2)

        cap_slugs2 = sorted(
            [cap.territory.slug for cap in Capital.objects.filter(territory__game=game2)]
        )

        self.assertEqual(cap_slugs, cap_slugs2)

    def test_atomicity_and_rollback_on_failure(self):
        """If an error occurs during initialization, all changes are rolled back."""
        with patch("games.services.validate_game_territories", side_effect=RuntimeError("Simulated error")):
            with self.assertRaises(RuntimeError):
                initialize_game(self.game)

        # Entire transaction rolled back
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.WAITING)
        self.assertEqual(self.game.territories.count(), 0)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 0)

    def test_independent_games(self):
        """Two separate games initialize independently without cross-game coupling."""
        game2 = Game.objects.create(status=Game.Status.WAITING)
        user_a = User.objects.create_user("ua", "ua@example.com", "pw")
        user_b = User.objects.create_user("ub", "ub@example.com", "pw")
        user_c = User.objects.create_user("uc", "uc@example.com", "pw")
        Player.objects.create(user=user_a, game=game2, color=Player.Color.RED)
        Player.objects.create(user=user_b, game=game2, color=Player.Color.GREEN)
        Player.objects.create(user=user_c, game=game2, color=Player.Color.BLUE)

        initialize_game(self.game)
        initialize_game(game2)

        self.assertEqual(self.game.territories.count(), 18)
        self.assertEqual(game2.territories.count(), 18)
        self.assertEqual(Territory.objects.count(), 36)

        # Modifying a territory in game 1 does not affect game 2
        t1 = self.game.territories.get(slug="skali")
        t2 = game2.territories.get(slug="skali")
        t1.score = 500
        t1.save()
        t2.refresh_from_db()
        self.assertEqual(t2.score, 0)

    def test_cannot_add_or_remove_player_after_game_start(self):
        """Players cannot be added to or removed from an active game."""
        initialize_game(self.game)
        self.assertEqual(self.game.status, Game.Status.ACTIVE)

        # Adding a player fails model validation
        new_u = User.objects.create_user("extra_u", "ex@example.com", "pw")
        extra_player = Player(user=new_u, game=self.game, color=Player.Color.RED)
        with self.assertRaises(ValidationError):
            extra_player.full_clean()

        # Removing a player via remove() fails validation
        with self.assertRaises(ValidationError):
            self.p1.remove()

    def test_create_game_does_not_auto_initialize(self):
        """Creating a Game instance does not automatically initialize territories or capitals."""
        fresh_game = Game.objects.create()
        self.assertEqual(fresh_game.status, Game.Status.WAITING)
        self.assertEqual(fresh_game.territories.count(), 0)
        self.assertEqual(Capital.objects.filter(territory__game=fresh_game).count(), 0)
