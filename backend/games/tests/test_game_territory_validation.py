from django.core.exceptions import ValidationError
from django.test import TestCase

from games.map import MAP_DEFINITION, validate_game_territories
from games.models import Game, Territory


class GameTerritoriesValidationTests(TestCase):
    """Tests for validating that a game's created territories match MAP_DEFINITION."""

    def _create_full_map_for_game(self, game):
        """Helper to create the full project map in a game."""
        territories = {}
        for item in MAP_DEFINITION:
            t = Territory.objects.create(
                game=game,
                slug=item["slug"],
                name=item["name"],
            )
            territories[item["slug"]] = t

        for item in MAP_DEFINITION:
            t = territories[item["slug"]]
            for nbr_slug in item["neighbors"]:
                t.neighbors.add(territories[nbr_slug])

        return territories

    def test_validate_game_territories_success(self):
        """Game with all 18 territories matching MAP_DEFINITION passes validation."""
        game = Game.objects.create()
        self._create_full_map_for_game(game)
        self.assertTrue(validate_game_territories(game))

    def test_validate_game_territories_missing_territory_fails(self):
        """Game missing one territory fails validation."""
        game = Game.objects.create()
        territories = self._create_full_map_for_game(game)
        territories["skali"].delete()
        with self.assertRaises(ValidationError):
            validate_game_territories(game)

    def test_validate_game_territories_wrong_name_fails(self):
        """Game with a territory having an unexpected name fails validation."""
        game = Game.objects.create()
        territories = self._create_full_map_for_game(game)
        t = territories["skali"]
        t.name = "Грешно Име"
        t.save()
        with self.assertRaises(ValidationError):
            validate_game_territories(game)

    def test_validate_game_territories_missing_neighbor_fails(self):
        """Game with a missing neighbor connection fails validation."""
        game = Game.objects.create()
        territories = self._create_full_map_for_game(game)
        # Remove connection between skali and dunaviya
        territories["skali"].neighbors.remove(territories["dunaviya"])
        with self.assertRaises(ValidationError):
            validate_game_territories(game)

    def test_validate_game_territories_extra_neighbor_fails(self):
        """Game with an unexpected extra neighbor connection fails validation."""
        game = Game.objects.create()
        territories = self._create_full_map_for_game(game)
        # Add connection between skali and kaliakra (not in MAP_DEFINITION)
        territories["skali"].neighbors.add(territories["kaliakra"])
        with self.assertRaises(ValidationError):
            validate_game_territories(game)

    def test_validate_game_territories_cross_game_neighbor_fails(self):
        """Game with a neighbor belonging to another game fails validation."""
        game1 = Game.objects.create()
        game2 = Game.objects.create()
        territories1 = self._create_full_map_for_game(game1)
        t_game2 = Territory.objects.create(game=game2, slug="foreign", name="Чужд")

        territories1["skali"].neighbors.add(t_game2)
        with self.assertRaises(ValidationError):
            validate_game_territories(game1)

    def test_validate_does_not_mutate_state(self):
        """Validation only inspects state without creating or modifying anything."""
        game = Game.objects.create(status=Game.Status.WAITING)
        self._create_full_map_for_game(game)

        initial_t_count = Territory.objects.count()
        validate_game_territories(game)

        self.assertEqual(Territory.objects.count(), initial_t_count)
        self.assertEqual(game.status, Game.Status.WAITING)
        self.assertEqual(game.players.count(), 0)
