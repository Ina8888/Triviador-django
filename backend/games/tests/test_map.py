from django.core.exceptions import ValidationError
from django.test import TestCase

from games.map import MAP_DEFINITION, validate_map_graph


class ProjectMapDefinitionTests(TestCase):
    """Tests for the project-wide map graph definition and validation rules."""

    def test_project_map_size_valid(self):
        """Map size must be between 9 and 21 and a multiple of 3 (our project chose 18)."""
        count = len(MAP_DEFINITION)
        self.assertEqual(count, 18)
        self.assertTrue(9 <= count <= 21)
        self.assertEqual(count % 3, 0)

    def test_project_map_unique_names_and_slugs(self):
        """Every territory must have a unique non-empty name and slug."""
        names = [t["name"] for t in MAP_DEFINITION]
        slugs = [t["slug"] for t in MAP_DEFINITION]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(slugs), len(set(slugs)))
        for name in names:
            self.assertTrue(bool(name.strip()))
        for slug in slugs:
            self.assertTrue(bool(slug.strip()))

    def test_project_map_symmetric_connections(self):
        """Neighbor connections must be symmetric."""
        adj = {t["slug"]: set(t["neighbors"]) for t in MAP_DEFINITION}
        for slug, neighbors in adj.items():
            for nbr in neighbors:
                self.assertIn(
                    slug,
                    adj[nbr],
                    f"Connection between '{slug}' and '{nbr}' is not symmetric.",
                )

    def test_project_map_min_neighbors(self):
        """Every territory must have at least 2 neighbors."""
        for t in MAP_DEFINITION:
            self.assertGreaterEqual(
                len(t["neighbors"]),
                2,
                f"Territory '{t['slug']}' has fewer than 2 neighbors.",
            )

    def test_project_map_no_self_references(self):
        """A territory cannot be its own neighbor."""
        for t in MAP_DEFINITION:
            self.assertNotIn(
                t["slug"],
                t["neighbors"],
                f"Territory '{t['slug']}' contains self-reference.",
            )

    def test_project_map_no_duplicate_neighbors(self):
        """A territory's neighbors list cannot contain duplicates."""
        for t in MAP_DEFINITION:
            self.assertEqual(
                len(t["neighbors"]),
                len(set(t["neighbors"])),
                f"Territory '{t['slug']}' contains duplicate neighbors.",
            )

    def test_project_map_graph_connectivity(self):
        """Graph must be fully connected (every node reachable from any node)."""
        self.assertTrue(validate_map_graph(MAP_DEFINITION))

    def test_project_map_contains_capital_triplets(self):
        """Graph must have at least one triplet of pairwise non-adjacent territories."""
        adj = {t["slug"]: set(t["neighbors"]) for t in MAP_DEFINITION}
        nodes = list(adj.keys())
        import itertools
        valid_triplets = []
        for a, b, c in itertools.combinations(nodes, 3):
            if b not in adj[a] and c not in adj[a] and c not in adj[b]:
                valid_triplets.append((a, b, c))
        self.assertGreater(
            len(valid_triplets),
            0,
            "No mutually non-adjacent triplet found for initial capitals.",
        )


class MapValidatorNegativeTests(TestCase):
    """Tests ensuring validate_map_graph rejects invalid graph configurations."""

    def test_reject_size_not_multiple_of_3(self):
        """Reject maps where node count is not a multiple of 3."""
        bad_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%10}", f"t{(i-1)%10}"]}
            for i in range(10)
        ]
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_size_below_9(self):
        """Reject maps with fewer than 9 territories."""
        bad_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%6}", f"t{(i-1)%6}"]}
            for i in range(6)
        ]
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_size_above_21(self):
        """Reject maps with more than 21 territories."""
        bad_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%24}", f"t{(i-1)%24}"]}
            for i in range(24)
        ]
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_asymmetric_neighbors(self):
        """Reject map with asymmetric neighbor relationship."""
        bad_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%9}", f"t{(i-1)%9}"]}
            for i in range(9)
        ]
        # break symmetry: t0 lists t3, but t3 doesn't list t0
        bad_map[0]["neighbors"].append("t3")
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_disconnected_graph(self):
        """Reject disconnected graph (two separate components)."""
        # component 1: t0, t1, t2, t3, t4, t5 (ring of 6)
        comp1 = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%6}", f"t{(i-1)%6}"]}
            for i in range(6)
        ]
        # component 2: t6, t7, t8 (ring of 3)
        comp2 = [
            {"slug": "t6", "name": "T6", "neighbors": ["t7", "t8"]},
            {"slug": "t7", "name": "T7", "neighbors": ["t6", "t8"]},
            {"slug": "t8", "name": "T8", "neighbors": ["t6", "t7"]},
        ]
        bad_map = comp1 + comp2
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_degree_less_than_2(self):
        """Reject map where a territory has fewer than 2 neighbors."""
        bad_map = [
            {"slug": f"t{i}", "name": f"T{i}", "neighbors": [f"t{(i+1)%9}", f"t{(i-1)%9}"]}
            for i in range(9)
        ]
        bad_map[0]["neighbors"] = ["t1"]
        bad_map[1]["neighbors"] = ["t0", "t2"]
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)

    def test_reject_graph_without_capital_triplet(self):
        """Reject graph where every pair of nodes are connected (no independent triplet of size 3)."""
        # Complete graph K_9: all 9 nodes connected to all other 8 nodes
        bad_map = [
            {
                "slug": f"t{i}",
                "name": f"T{i}",
                "neighbors": [f"t{j}" for j in range(9) if j != i],
            }
            for i in range(9)
        ]
        with self.assertRaises(ValidationError):
            validate_map_graph(bad_map)
