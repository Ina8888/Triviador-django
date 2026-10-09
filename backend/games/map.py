"""Project-wide map definition and validation utilities for Quiz Conquest.

M04 defines the static map for the project: 18 territories with Bulgarian fantasy/historical
names and symmetric adjacencies.
Game initialization occurs in M05; M04 defines and validates the graph structure.
"""

from collections import deque
import itertools
from django.core.exceptions import ValidationError

MAP_DEFINITION = [
    {
        "slug": "skali",
        "name": "Скали",
        "neighbors": ["dunaviya", "sredets"],
    },
    {
        "slug": "dunaviya",
        "name": "Дунавия",
        "neighbors": ["skali", "zhitno-pole", "sredets"],
    },
    {
        "slug": "zhitno-pole",
        "name": "Житно поле",
        "neighbors": ["dunaviya", "leventa", "balkania"],
    },
    {
        "slug": "leventa",
        "name": "Левента",
        "neighbors": ["zhitno-pole", "pelikania", "madara"],
    },
    {
        "slug": "pelikania",
        "name": "Пеликания",
        "neighbors": ["leventa", "kaliakra", "madara"],
    },
    {
        "slug": "kaliakra",
        "name": "Калиакра",
        "neighbors": ["pelikania", "madara", "slanchevo"],
    },
    {
        "slug": "sredets",
        "name": "Средец",
        "neighbors": ["skali", "dunaviya", "ezera", "balkania", "rozova-dolina"],
    },
    {
        "slug": "balkania",
        "name": "Балкания",
        "neighbors": ["zhitno-pole", "sredets", "tsarevo", "rozova-dolina"],
    },
    {
        "slug": "tsarevo",
        "name": "Царево",
        "neighbors": ["balkania", "madara", "chuden-kray", "rozova-dolina"],
    },
    {
        "slug": "madara",
        "name": "Мадара",
        "neighbors": ["leventa", "pelikania", "kaliakra", "tsarevo", "chuden-kray"],
    },
    {
        "slug": "ezera",
        "name": "Езера",
        "neighbors": ["sredets", "pirina", "rozova-dolina"],
    },
    {
        "slug": "pirina",
        "name": "Пирина",
        "neighbors": ["ezera", "zlaten-grozd", "karakachan"],
    },
    {
        "slug": "rozova-dolina",
        "name": "Розова долина",
        "neighbors": ["sredets", "balkania", "tsarevo", "ezera", "zlaten-grozd"],
    },
    {
        "slug": "chuden-kray",
        "name": "Чуден край",
        "neighbors": ["tsarevo", "madara", "kukeri", "slanchevo"],
    },
    {
        "slug": "zlaten-grozd",
        "name": "Златен грозд",
        "neighbors": ["rozova-dolina", "pirina", "karakachan", "kukeri"],
    },
    {
        "slug": "kukeri",
        "name": "Кукери",
        "neighbors": ["zlaten-grozd", "chuden-kray", "karakachan", "slanchevo"],
    },
    {
        "slug": "karakachan",
        "name": "Каракачан",
        "neighbors": ["pirina", "zlaten-grozd", "kukeri"],
    },
    {
        "slug": "slanchevo",
        "name": "Слънчево",
        "neighbors": ["kaliakra", "chuden-kray", "kukeri"],
    },
]

# Quick lookup by slug
MAP_BY_SLUG = {t["slug"]: t for t in MAP_DEFINITION}


def validate_map_graph(definition=None):
    """Validate graph rules for a map definition.

    Rules:
    - Size between 9 and 21 inclusive, multiple of 3.
    - Unique slugs and names.
    - Symmetric neighbor relations: if A in neighbors(B), B in neighbors(A).
    - No self-reference: A not in neighbors(A).
    - No duplicate neighbors.
    - Minimum degree: each territory has >= 2 neighbors.
    - Connectivity: all territories can reach all other territories.
    - Initial capitals: at least one triplet of pairwise non-adjacent territories exists.
    """
    if definition is None:
        definition = MAP_DEFINITION

    count = len(definition)
    if count < 9 or count > 21 or count % 3 != 0:
        raise ValidationError(
            f"Map size must be between 9 and 21 and a multiple of 3. Got {count}."
        )

    slugs = set()
    names = set()
    adj = {}

    for t in definition:
        slug = t.get("slug")
        name = t.get("name")
        neighbors = t.get("neighbors", [])

        if not slug or not name:
            raise ValidationError("Every territory must have a non-empty 'slug' and 'name'.")

        if slug in slugs:
            raise ValidationError(f"Duplicate slug '{slug}' in map definition.")
        if name in names:
            raise ValidationError(f"Duplicate name '{name}' in map definition.")

        slugs.add(slug)
        names.add(name)

        if len(neighbors) != len(set(neighbors)):
            raise ValidationError(f"Territory '{slug}' contains duplicate neighbors.")

        if slug in neighbors:
            raise ValidationError(f"Territory '{slug}' cannot be neighbor to itself.")

        if len(neighbors) < 2:
            raise ValidationError(
                f"Territory '{slug}' must have at least 2 neighbors, found {len(neighbors)}."
            )

        adj[slug] = set(neighbors)

    for slug, nbrs in adj.items():
        for nbr in nbrs:
            if nbr not in slugs:
                raise ValidationError(
                    f"Territory '{slug}' references unknown neighbor '{nbr}'."
                )

    for slug, nbrs in adj.items():
        for nbr in nbrs:
            if slug not in adj[nbr]:
                raise ValidationError(
                    f"Asymmetric connection: '{slug}' has neighbor '{nbr}', but not vice-versa."
                )

#bfs
    start = next(iter(slugs))
    visited = set()
    queue = deque([start])
    visited.add(start)
    while queue:
        curr = queue.popleft()
        for nbr in adj[curr]:
            if nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)

    if len(visited) != count:
        raise ValidationError(
            f"Graph is not connected: reached {len(visited)} of {count} territories."
        )

    all_slugs = list(slugs)
    has_valid_triplet = False
    for a, b, c in itertools.combinations(all_slugs, 3):
        if b not in adj[a] and c not in adj[a] and c not in adj[b]:
            has_valid_triplet = True
            break

    if not has_valid_triplet:
        raise ValidationError(
            "Graph must contain at least one triplet of pairwise non-adjacent territories for capitals."
        )

    return True


def validate_game_territories(game):
    """Validate that a game's created territories match the project MAP_DEFINITION.

    Checks:
    - Territory count matches MAP_DEFINITION (18).
    - Every slug and name matches the expected definition.
    - All territories belong to the specified game.
    - Neighbor connections in the database match MAP_DEFINITION exactly.
    """
    territories = list(game.territories.all())
    expected_count = len(MAP_DEFINITION)

    if len(territories) != expected_count:
        raise ValidationError(
            f"Game #{game.pk} has {len(territories)} territories; expected {expected_count}."
        )

    territories_by_slug = {}
    for t in territories:
        if t.game_id != game.pk:
            raise ValidationError(
                f"Territory '{t.slug}' belongs to Game #{t.game_id}, not Game #{game.pk}."
            )
        territories_by_slug[t.slug] = t

    expected_slugs = {item["slug"] for item in MAP_DEFINITION}
    actual_slugs = set(territories_by_slug.keys())

    if actual_slugs != expected_slugs:
        missing = expected_slugs - actual_slugs
        extra = actual_slugs - expected_slugs
        raise ValidationError(
            f"Game territories mismatch. Missing: {missing}, Extra: {extra}."
        )

    for item in MAP_DEFINITION:
        slug = item["slug"]
        expected_name = item["name"]
        expected_neighbors = set(item["neighbors"])

        t = territories_by_slug[slug]
        if t.name != expected_name:
            raise ValidationError(
                f"Territory '{slug}' has name '{t.name}'; expected '{expected_name}'."
            )

        actual_neighbors = {n.slug for n in t.neighbors.all()}
        for n in t.neighbors.all():
            if n.game_id != game.pk:
                raise ValidationError(
                    f"Territory '{slug}' has cross-game neighbor '{n.slug}' from Game #{n.game_id}."
                )

        if actual_neighbors != expected_neighbors:
            raise ValidationError(
                f"Territory '{slug}' neighbors mismatch. "
                f"Actual: {actual_neighbors}, Expected: {expected_neighbors}."
            )

    return True
