from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from games.admin import CapitalAdmin, TerritoryAdmin
from games.models import Capital, Game, Player, Territory

User = get_user_model()


class DummyRequest:
    pass


class AdminConfigurationTests(TestCase):
    """Tests for TerritoryAdmin and CapitalAdmin configuration and structural protection."""

    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.territory_admin = TerritoryAdmin(Territory, self.site)
        self.capital_admin = CapitalAdmin(Capital, self.site)

        self.game = Game.objects.create()
        self.user = User.objects.create_user(
            username="admin_u", email="admin_u@example.com", password="pw"
        )
        self.player = Player.objects.create(
            user=self.user, game=self.game, color=Player.Color.RED
        )
        self.territory = Territory.objects.create(
            game=self.game, name="Средец", slug="sredets", owner=self.player
        )
        self.capital = Capital.objects.create(
            territory=self.territory, player=self.player, health=3
        )

    def test_territory_admin_list_display_and_filters(self):
        """TerritoryAdmin provides required display, filters, and search fields."""
        self.assertIn("name", self.territory_admin.list_display)
        self.assertIn("slug", self.territory_admin.list_display)
        self.assertIn("game", self.territory_admin.list_display)
        self.assertIn("owner", self.territory_admin.list_display)
        self.assertIn("score", self.territory_admin.list_display)
        self.assertIn("neighbors_display", self.territory_admin.list_display)

        self.assertIn("name", self.territory_admin.search_fields)
        self.assertIn("slug", self.territory_admin.search_fields)

        self.assertIn("game", self.territory_admin.list_filter)
        self.assertIn("owner", self.territory_admin.list_filter)

    def test_capital_admin_list_display_and_filters(self):
        """CapitalAdmin provides required display, filters, and search fields."""
        self.assertIn("player", self.capital_admin.list_display)
        self.assertIn("territory", self.capital_admin.list_display)
        self.assertIn("health", self.capital_admin.list_display)
        self.assertIn("get_game", self.capital_admin.list_display)

        self.assertIn("player__user__username", self.capital_admin.search_fields)
        self.assertIn("territory__name", self.capital_admin.search_fields)

        self.assertIn("territory__game", self.capital_admin.list_filter)

    def test_territory_admin_structural_protection(self):
        """Admin prohibits adding or deleting territories to protect map structure."""
        self.assertFalse(self.territory_admin.has_add_permission(self.request))
        self.assertFalse(
            self.territory_admin.has_delete_permission(self.request, self.territory)
        )
        readonly = self.territory_admin.get_readonly_fields(self.request, self.territory)
        self.assertIn("game", readonly)
        self.assertIn("name", readonly)
        self.assertIn("slug", readonly)
        self.assertIn("neighbors", readonly)

    def test_capital_admin_structural_protection(self):
        """Admin prohibits adding or deleting capitals and protects player/territory links."""
        self.assertFalse(self.capital_admin.has_add_permission(self.request))
        self.assertFalse(
            self.capital_admin.has_delete_permission(self.request, self.capital)
        )
        readonly = self.capital_admin.get_readonly_fields(self.request, self.capital)
        self.assertIn("player", readonly)
        self.assertIn("territory", readonly)

    def test_territory_admin_save_model_validates_rules(self):
        """Saving via admin executes full_clean() so invalid values are rejected."""
        self.territory.score = -10
        with self.assertRaises(ValidationError):
            self.territory_admin.save_model(
                self.request, self.territory, form=None, change=True
            )

    def test_capital_admin_save_model_validates_rules(self):
        """Saving capital via admin executes full_clean() so invalid health is rejected."""
        self.capital.health = 5
        with self.assertRaises(ValidationError):
            self.capital_admin.save_model(
                self.request, self.capital, form=None, change=True
            )
