from django.contrib import admin
from .models import (
    Capital,
    CaptureRight,
    Game,
    Player,
    Round,
    RoundAnswer,
    RoundPlacement,
    RoundQuestion,
    Territory,
    TerritoryCaptureLog,
)


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    fields = ("user", "color", "score")


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0
    fields = ("number", "type", "status", "winner", "completion_reason", "created_at", "completed_at")
    readonly_fields = ("created_at",)


class RoundQuestionInline(admin.TabularInline):
    model = RoundQuestion
    extra = 0
    fields = ("sequence", "status", "question_text", "correct_answer", "started_at", "deadline")
    readonly_fields = ("sequence", "question_text", "correct_answer", "started_at", "deadline")


class RoundPlacementInline(admin.TabularInline):
    model = RoundPlacement
    extra = 0
    fields = ("place", "player")
    readonly_fields = ("place", "player")


class CaptureRightInline(admin.TabularInline):
    model = CaptureRight
    extra = 0
    fields = ("order", "player", "allowed_choices", "used_choices")
    readonly_fields = ("order", "player", "allowed_choices", "used_choices")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "status", "player_count")
    list_filter = ("status",)
    inlines = [PlayerInline, RoundInline]

    @admin.display(description="Players")
    def player_count(self, obj):
        return obj.players.count()


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("user", "game", "color", "score")
    list_filter = ("game", "color")
    search_fields = ("user__username",)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.game.status != Game.Status.WAITING:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("game", "number", "type", "status", "winner", "completion_reason", "created_at", "completed_at")
    list_filter = ("game", "type", "status")
    inlines = [RoundQuestionInline, RoundPlacementInline, CaptureRightInline]


@admin.register(RoundQuestion)
class RoundQuestionAdmin(admin.ModelAdmin):
    list_display = ("round", "sequence", "status", "question_text", "correct_answer", "started_at", "deadline")
    list_filter = ("status", "round__game")


@admin.register(RoundAnswer)
class RoundAnswerAdmin(admin.ModelAdmin):
    list_display = ("round_question", "player", "answer", "difference", "submitted_at")
    list_filter = ("round_question__round__game",)


@admin.register(RoundPlacement)
class RoundPlacementAdmin(admin.ModelAdmin):
    list_display = ("round", "place", "player")
    list_filter = ("round__game", "place")


@admin.register(CaptureRight)
class CaptureRightAdmin(admin.ModelAdmin):
    list_display = ("round", "order", "player", "allowed_choices", "used_choices")
    list_filter = ("round__game", "order")


@admin.register(TerritoryCaptureLog)
class TerritoryCaptureLogAdmin(admin.ModelAdmin):
    list_display = ("round", "player", "territory", "points_awarded", "player_score_after", "territory_score_after", "captured_at")
    list_filter = ("round__game", "player")


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "game", "owner", "score", "neighbors_display")
    search_fields = ("name", "slug")
    list_filter = ("game", "owner")
    readonly_fields = ("neighbors_display",)

    @admin.display(description="Neighbors")
    def neighbors_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        return ", ".join(n.slug for n in obj.neighbors.all()) or "-"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("game", "name", "slug", "neighbors") + self.readonly_fields
        return self.readonly_fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Capital)
class CapitalAdmin(admin.ModelAdmin):
    list_display = ("player", "territory", "health", "get_game")
    search_fields = ("player__user__username", "territory__name")
    list_filter = ("territory__game",)

    @admin.display(description="Game")
    def get_game(self, obj):
        return obj.territory.game if obj.territory else "-"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("player", "territory")
        return ()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
