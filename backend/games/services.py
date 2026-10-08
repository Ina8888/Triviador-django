"""Service layer for Game Initialization (M05).

Prepares the initial game state:
- Validates game status and player count.
- Prevents re-initialization or partial initialization.
- Randomly assigns mutually non-adjacent capitals to all 3 players.
- Creates all 18 territories and symmetric neighbor links from MAP_DEFINITION.
- Transitions game status to 'active' atomically.
"""

import itertools
import random
from django.core.exceptions import ValidationError
from django.db import transaction

from .map import MAP_DEFINITION, validate_map_graph, validate_game_territories
from .models import Capital, Game, Territory


def get_valid_capital_triplets(map_definition):
    """Find all triplets of mutually non-adjacent territories in the given map definition."""
    adj = {t["slug"]: set(t["neighbors"]) for t in map_definition}
    slugs = list(adj.keys())

    triplets = []
    for a, b, c in itertools.combinations(slugs, 3):
        if b not in adj[a] and c not in adj[a] and c not in adj[b]:
            triplets.append((a, b, c))

    return triplets


def initialize_game(game, random_generator=None, map_definition=None):
    """Initialize a game's territories, assign capitals to the 3 players, and activate game.

    Parameters:
    - game: The Game instance to initialize.
    - random_generator: Optional custom RNG (e.g. random.Random(seed)) for deterministic testing.
    - map_definition: Optional map definition (defaults to M04 project MAP_DEFINITION).

    Pre-conditions:
    - Game exists and has status 'waiting'.
    - Game has exactly 3 players.
    - Game does not have existing territories or capitals.
    - Map definition is valid per M04 rules.
    - At least one valid capital triplet exists.

    Atomicity:
    All creations and status change occur within an atomic transaction. Any error rolls back
    completely, leaving the game in its previous state.
    """
    if map_definition is None:
        map_definition = MAP_DEFINITION

    # 1. Validate preconditions before starting transaction
    if game.status != Game.Status.WAITING:
        raise ValidationError(
            f"Cannot initialize Game #{game.pk} with status '{game.status}'. Game must be 'waiting'."
        )

    player_count = game.players.count()
    if player_count != 3:
        raise ValidationError(
            f"Game #{game.pk} has {player_count} player(s). Exactly 3 players are required to start."
        )

    if game.territories.exists():
        raise ValidationError(
            f"Game #{game.pk} already has territories. Repeat or partial initialization is not allowed."
        )

    if Capital.objects.filter(territory__game=game).exists():
        raise ValidationError(
            f"Game #{game.pk} already has capitals assigned."
        )

    # 2. Validate map definition
    validate_map_graph(map_definition)

    # 3. Find valid capital triplets
    triplets = get_valid_capital_triplets(map_definition)
    if not triplets:
        raise ValidationError(
            "Map definition does not contain any valid triplet of mutually non-adjacent territories for capitals."
        )

    # 4. Choose a triplet of non-adjacent capitals
    rng = random_generator or random
    if hasattr(rng, "choice"):
        selected_triplet = list(rng.choice(triplets))
    else:
        selected_triplet = list(random.choice(triplets))

    if hasattr(rng, "shuffle"):
        rng.shuffle(selected_triplet)
    else:
        random.shuffle(selected_triplet)

    # 5. Atomic initialization
    with transaction.atomic():
        # Select for update where supported (concurrency safety)
        try:
            locked_game = Game.objects.select_for_update().get(pk=game.pk)
        except Exception:
            locked_game = Game.objects.get(pk=game.pk)

        # Re-check under lock in case another transaction ran concurrently
        if locked_game.status != Game.Status.WAITING:
            raise ValidationError(
                f"Game #{locked_game.pk} is already '{locked_game.status}'. Cannot initialize again."
            )
        if locked_game.territories.exists():
            raise ValidationError(
                f"Game #{locked_game.pk} already has territories created."
            )
        if locked_game.players.count() != 3:
            raise ValidationError(
                f"Game #{locked_game.pk} must have exactly 3 players to initialize."
            )

        players = list(locked_game.players.order_by("pk"))
        # Map each player to one chosen capital slug
        player_capitals = dict(zip(players, selected_triplet))

        # Create all territory instances
        territory_map = {}
        for item in map_definition:
            slug = item["slug"]
            name = item["name"]

            # Set owner if this territory is a capital
            owner = None
            for player, cap_slug in player_capitals.items():
                if cap_slug == slug:
                    owner = player
                    break

            t = Territory.objects.create(
                game=locked_game,
                slug=slug,
                name=name,
                owner=owner,
                score=0,
            )
            territory_map[slug] = t

        # Connect neighbors symmetrically
        for item in map_definition:
            t = territory_map[item["slug"]]
            for nbr_slug in item["neighbors"]:
                t.neighbors.add(territory_map[nbr_slug])

        # Create Capital fortress records for each player
        for player, cap_slug in player_capitals.items():
            cap_territory = territory_map[cap_slug]
            Capital.objects.create(
                player=player,
                territory=cap_territory,
                health=3,
            )

        # Transition game status to active
        locked_game.status = Game.Status.ACTIVE
        locked_game.save()

        # Validate that created game territories match project definition exactly
        validate_game_territories(locked_game)

    # Refresh original game instance
    game.refresh_from_db()
    return game
