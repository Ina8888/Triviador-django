from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone


class Game(models.Model):
    """A single game session with exactly 3 players."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.WAITING,
    )

    def get_current_round(self):
        """Return the round with the highest number in this game."""
        return self.rounds.order_by("-number").first()

    def is_active(self):
        return self.status == self.Status.ACTIVE

    def is_completed(self):
        return self.status == self.Status.COMPLETED

    def start(self):
        """Start game. Allowed only when exactly 3 players have joined."""
        if self.players.count() != 3:
            raise ValidationError("Game requires exactly 3 players to start.")
        self.status = self.Status.ACTIVE
        self.save()

    def complete(self):
        """Complete the game."""
        self.status = self.Status.COMPLETED
        self.save()

    def initialize(self, random_generator=None, map_definition=None):
        """Initialize game: create territories, assign capitals, and transition to active."""
        from .services import initialize_game
        return initialize_game(self, random_generator=random_generator, map_definition=map_definition)

    def __str__(self):
        return f"Game #{self.pk} ({self.status})"


class Player(models.Model):
    """A user's participation in a specific game with a unique color."""

    class Color(models.TextChoices):
        RED = "red", "Red"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="players",
    )
    score = models.IntegerField(default=0)
    color = models.CharField(
        max_length=5,
        choices=Color.choices,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "game"],
                name="unique_user_per_game",
            ),
            models.UniqueConstraint(
                fields=["game", "color"],
                name="unique_color_per_game",
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0),
                name="player_score_gte_0",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.pk and self.game_id:
            if self.game.status != Game.Status.WAITING:
                raise ValidationError("Cannot add players to an active or completed game.")
            if self.game.players.count() >= 3:
                raise ValidationError("A game cannot have more than 3 players.")

    def remove(self):
        """Application operation to remove player from a game prior to start."""
        if self.game.status != Game.Status.WAITING:
            raise ValidationError("Cannot remove players from an active or completed game.")
        self.delete()

    def get_capital(self):
        """Return the player's capital if one exists, otherwise None."""
        try:
            return self.capital
        except ObjectDoesNotExist:
            return None

    def __str__(self):
        return f"{self.user} in Game #{self.game_id} ({self.color})"


class Round(models.Model):
    """A single round within a game."""

    class Type(models.TextChoices):
        CITY_CAPTURE = "city_capture", "City Capture"
        BATTLE = "battle", "Battle"
        CAPITAL_ATTACK = "capital_attack", "Capital Attack"
        BONUS = "bonus", "Bonus"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    number = models.PositiveIntegerField()
    type = models.CharField(
        max_length=15,
        choices=Type.choices,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    winner = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    completion_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "number"],
                name="unique_round_number_per_game",
            ),
        ]

    def clean(self):
        super().clean()
        # Winner must belong to the same game
        if self.winner is not None and self.winner.game_id != self.game_id:
            raise ValidationError(
                {"winner": "Winner must be a player of the same game."}
            )
        # Completed round must have completed_at
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            raise ValidationError(
                {"completed_at": "Completed round must have completed_at timestamp."}
            )
        # Completed round without winner must have a completion_reason
        if self.status == self.Status.COMPLETED and self.winner is None and not self.completion_reason:
            raise ValidationError(
                {"winner": "Completed round without winner must specify a completion_reason."}
            )

    def complete(self, winner=None, completion_reason=None):
        """Mark round as completed with optional winner, reason and timestamp."""
        if winner is not None and winner.game_id != self.game_id:
            raise ValidationError({"winner": "Winner must be a player of the same game."})
        self.winner = winner
        self.completion_reason = completion_reason
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.full_clean()
        self.save()

    def get_current_question(self):
        """Return the current or latest asked question for this round."""
        return self.questions.order_by("-sequence").first()

    def get_placements(self):
        """Return the recorded placements for this round ordered by place."""
        return self.placements.order_by("place")

    def __str__(self):
        return f"Round {self.number} of Game #{self.game_id} ({self.status})"


class RoundQuestion(models.Model):
    """An asked question within a round, preserving snapshot content and timing."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question = models.ForeignKey(
        "questions.NumericQuestion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="round_questions",
    )
    sequence = models.PositiveIntegerField(default=1)
    question_text = models.TextField()
    correct_answer = models.IntegerField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    participants = models.ManyToManyField(
        Player,
        related_name="round_questions",
        blank=True,
    )

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "sequence"],
                name="unique_question_sequence_per_round",
            ),
        ]

    def get_remaining_seconds(self, current_time=None):
        """Return remaining seconds until deadline, or 0.0 if not active/expired."""
        if not self.deadline or self.status != self.Status.ACTIVE:
            return 0.0
        now = current_time or timezone.now()
        remaining = (self.deadline - now).total_seconds()
        return max(0.0, remaining)

    def is_expired(self, current_time=None):
        """Return True if the deadline has arrived or passed."""
        if not self.deadline:
            return False
        now = current_time or timezone.now()
        return now >= self.deadline

    def __str__(self):
        return f"Q#{self.sequence} for Round #{self.round_id} ({self.status})"


class RoundAnswer(models.Model):
    """An accepted answer submitted by a player for a specific round question."""

    round_question = models.ForeignKey(
        RoundQuestion,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="round_answers",
    )
    answer = models.IntegerField()
    difference = models.PositiveIntegerField()
    submitted_at = models.DateTimeField()

    class Meta:
        ordering = ["difference", "submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["round_question", "player"],
                name="unique_player_answer_per_question",
            ),
        ]

    def __str__(self):
        return f"{self.player} answered {self.answer} (diff: {self.difference})"


class RoundPlacement(models.Model):
    """Recorded placement (1st, 2nd place, etc.) for a round."""

    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="placements",
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="round_placements",
    )
    place = models.PositiveIntegerField()

    class Meta:
        ordering = ["place"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "place"],
                name="unique_place_per_round",
            ),
            models.UniqueConstraint(
                fields=["round", "player"],
                name="unique_player_per_round_placement",
            ),
        ]

    def __str__(self):
        return f"Place {self.place}: {self.player}"


class Territory(models.Model):
    """A map territory belonging to a specific game session."""

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="territories",
    )
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50)
    neighbors = models.ManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
    )
    owner = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="territories",
    )
    score = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "name"],
                name="unique_territory_name_per_game",
            ),
            models.UniqueConstraint(
                fields=["game", "slug"],
                name="unique_territory_slug_per_game",
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0),
                name="territory_score_gte_0",
            ),
        ]

    def clean(self):
        super().clean()
        if self.score is not None and self.score < 0:
            raise ValidationError({"score": "Territory score cannot be negative."})
        if self.owner_id and self.owner.game_id != self.game_id:
            raise ValidationError({"owner": "Territory owner must belong to the same game."})
        if self.pk:
            for neighbor in self.neighbors.all():
                if neighbor.game_id != self.game_id:
                    raise ValidationError(
                        {"neighbors": f"Neighbor '{neighbor.slug}' belongs to a different game."}
                    )
                if neighbor.pk == self.pk:
                    raise ValidationError(
                        {"neighbors": "A territory cannot be its own neighbor."}
                    )

    def __str__(self):
        return f"{self.name} ({self.slug}) [Game #{self.game_id}]"


class Capital(models.Model):
    """The capital fortress of a player on a specific territory."""

    territory = models.OneToOneField(
        Territory,
        on_delete=models.CASCADE,
        related_name="capital",
    )
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name="capital",
    )
    health = models.IntegerField(default=3)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(health__gte=0, health__lte=3),
                name="capital_health_between_0_and_3",
            ),
        ]

    def clean(self):
        super().clean()
        if self.health is not None and (self.health < 0 or self.health > 3):
            raise ValidationError({"health": "Capital health must be between 0 and 3."})
        if self.player_id and self.territory_id:
            if self.player.game_id != self.territory.game_id:
                raise ValidationError("Player and territory must belong to the same game.")
            if self.territory.owner_id != self.player_id:
                raise ValidationError(
                    {"territory": "Capital territory must be owned by the capital player."}
                )

    def __str__(self):
        return f"Capital of {self.player} at {self.territory.name} (Health: {self.health})"
