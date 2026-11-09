"""Service layer for Game Initialization (M05), Round Lifecycle (M06), and Territory Capture & Scoring (M07)."""

from datetime import timedelta
import itertools
import random
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from questions.models import AnswerOption, ChoiceQuestion, NumericQuestion
from .exceptions import GameError, InvalidInputError, InvalidStateError, RecordNotFoundError
from .map import MAP_DEFINITION, validate_map_graph, validate_game_territories
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

# ==============================================================================
# Scoring Constants (M07)
# ==============================================================================
ROUND_VICTORY_REWARD = 100       # Points awarded to round winner upon round completion
TERRITORY_CAPTURE_REWARD = 200   # Points awarded to player for capturing a territory
TERRITORY_SCORE_INCREMENT = 100  # Amount added to Territory.score upon capture (0 -> 100)


# ==============================================================================
# M05 — Game Initialization
# ==============================================================================

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
    """Initialize a game's territories, assign capitals to the 3 players, and activate game."""
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
        try:
            locked_game = Game.objects.select_for_update().get(pk=game.pk)
        except Exception:
            locked_game = Game.objects.get(pk=game.pk)

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
        player_capitals = dict(zip(players, selected_triplet))

        territory_map = {}
        for item in map_definition:
            slug = item["slug"]
            name = item["name"]

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

        for item in map_definition:
            t = territory_map[item["slug"]]
            for nbr_slug in item["neighbors"]:
                t.neighbors.add(territory_map[nbr_slug])

        for player, cap_slug in player_capitals.items():
            cap_territory = territory_map[cap_slug]
            Capital.objects.create(
                player=player,
                territory=cap_territory,
                health=3,
            )

        locked_game.status = Game.Status.ACTIVE
        locked_game.save()

        validate_game_territories(locked_game)

    game.refresh_from_db()
    return game


# ==============================================================================
# M06 — Round Lifecycle Operations
# ==============================================================================

def has_pending_capture_rights(game):
    """Return True if the game has unfulfilled capture rights and free territories remain."""
    if not game.territories.filter(owner__isnull=True).exists():
        return False
    latest_completed = game.rounds.filter(
        type=Round.Type.CITY_CAPTURE,
        status=Round.Status.COMPLETED,
    ).order_by("-number").first()
    if not latest_completed:
        return False
    return latest_completed.capture_rights.filter(used_choices__lt=models.F("allowed_choices")).exists()


def create_round(
    game,
    round_type=None,
    question=None,
    attacker=None,
    target_territory=None,
    defender=None,
    random_generator=None,
):
    """Create a new round in 'pending' status.

    Preconditions:
    - Game must be 'active'.
    - Game must have exactly 3 players.
    - Game cannot have an existing uncompleted round (at most one pending/active round).
    - Previous round must not have unfulfilled territory capture rights.
    - For city_capture: conquest phase must not be completed (at least 1 free territory needed).
    - For battle / capital_attack: all territories must be captured (0 free territories),
      attacker must be in game, target must belong to game, not be free, not owned by attacker,
      adjacent to at least one attacker territory; defender is target.owner.
    """
    if game.status != Game.Status.ACTIVE:
        raise InvalidStateError(f"Cannot create round for game in '{game.status}' status (must be active).")

    if game.players.count() != 3:
        raise InvalidStateError("Game must have exactly 3 players to create a round.")

    if game.rounds.filter(status__in=[Round.Status.PENDING, Round.Status.ACTIVE]).exists():
        raise InvalidStateError("Cannot create a new round: game already has an uncompleted round.")

    if has_pending_capture_rights(game):
        raise InvalidStateError("Cannot create a new round: unfulfilled territory capture rights remain in the previous round.")

    is_battle = (
        round_type in (Round.Type.BATTLE, Round.Type.CAPITAL_ATTACK)
        or target_territory is not None
        or attacker is not None
    )

    if is_battle:
        # All territories must be captured before battles can begin
        free_count = game.territories.filter(owner__isnull=True).count()
        if free_count > 0:
            raise InvalidStateError("Cannot start battles while free territories remain on the map.")

        if attacker is None or attacker.game_id != game.id:
            raise InvalidInputError("Attacker must be a player in this game.")

        if target_territory is None or target_territory.game_id != game.id:
            raise InvalidInputError("Target territory must belong to this game.")

        if target_territory.owner is None:
            raise InvalidInputError("Target territory cannot be free.")

        if target_territory.owner == attacker:
            raise InvalidInputError("Cannot attack own territory.")

        if not target_territory.neighbors.filter(owner=attacker).exists():
            raise InvalidInputError("Target territory must be adjacent to at least one territory owned by attacker.")

        real_defender = target_territory.owner
        if defender is not None and defender != real_defender:
            raise InvalidInputError("Provided defender does not match target territory owner.")
        defender = real_defender

        is_capital = Capital.objects.filter(territory=target_territory).exists()
        expected_type = Round.Type.CAPITAL_ATTACK if is_capital else Round.Type.BATTLE
        if round_type is not None and round_type != expected_type:
            raise InvalidInputError(f"Target territory requires round type '{expected_type}', not '{round_type}'.")
        round_type = expected_type

        # Select ChoiceQuestion
        used_choice_ids = RoundQuestion.objects.filter(
            round__game=game, choice_question__isnull=False
        ).values_list("choice_question_id", flat=True)

        if question is not None:
            if not isinstance(question, ChoiceQuestion):
                raise InvalidInputError("Question for battle round must be a ChoiceQuestion.")
            if question.id in used_choice_ids:
                raise InvalidInputError("The specified choice question has already been used in this game.")
            if question.options.count() != 4 or question.options.filter(is_correct=True).count() != 1:
                raise InvalidInputError("ChoiceQuestion must have exactly 4 options with exactly 1 correct answer.")
            selected_choice_q = question
        else:
            available_choice = list(
                ChoiceQuestion.objects.exclude(id__in=used_choice_ids)
                .annotate(
                    opt_count=models.Count("options"),
                    correct_count=models.Count("options", filter=models.Q(options__is_correct=True)),
                )
                .filter(opt_count=4, correct_count=1)
            )
            if not available_choice:
                raise RecordNotFoundError("No unused choice questions available in question bank.")
            rng = random_generator or random
            selected_choice_q = rng.choice(available_choice)

        max_num = game.rounds.aggregate(models.Max("number"))["number__max"]
        round_number = (max_num + 1) if max_num is not None else 1

        with transaction.atomic():
            round_obj = Round.objects.create(
                game=game,
                number=round_number,
                type=round_type,
                status=Round.Status.PENDING,
                attacker=attacker,
                defender=defender,
                target_territory=target_territory,
                winner=None,
                completed_at=None,
            )
            round_q = RoundQuestion.objects.create(
                round=round_obj,
                question_type=RoundQuestion.QuestionType.CHOICE,
                choice_question=selected_choice_q,
                sequence=1,
                question_text=selected_choice_q.text,
                correct_answer=None,
                status=RoundQuestion.Status.PENDING,
                started_at=None,
                deadline=None,
            )
            round_q.participants.set([attacker, defender])

        return round_obj

    # Default to CITY_CAPTURE
    round_type = round_type or Round.Type.CITY_CAPTURE
    if round_type == Round.Type.CITY_CAPTURE and game.territories.exists():
        free_count = game.territories.filter(owner__isnull=True).count()
        if free_count == 0:
            raise InvalidStateError("Conquest phase completed: all territories have been captured. Cannot create city_capture round.")

    # Find unused numeric questions in this game
    used_question_ids = RoundQuestion.objects.filter(
        round__game=game, question__isnull=False
    ).values_list("question_id", flat=True)

    if question is None:
        available_questions = list(NumericQuestion.objects.exclude(id__in=used_question_ids))
        if not available_questions:
            raise RecordNotFoundError("No unused numeric questions available in question bank.")
        rng = random_generator or random
        selected_question = rng.choice(available_questions)
    else:
        if question.id in used_question_ids:
            raise InvalidInputError("The specified question has already been used in this game.")
        selected_question = question

    # Compute next round number (1 if first, else max existing + 1; gaps preserved)
    max_num = game.rounds.aggregate(models.Max("number"))["number__max"]
    round_number = (max_num + 1) if max_num is not None else 1

    with transaction.atomic():
        round_obj = Round.objects.create(
            game=game,
            number=round_number,
            type=round_type,
            status=Round.Status.PENDING,
            winner=None,
            completed_at=None,
        )

        round_q = RoundQuestion.objects.create(
            round=round_obj,
            question_type=RoundQuestion.QuestionType.NUMERIC,
            question=selected_question,
            sequence=1,
            question_text=selected_question.text,
            correct_answer=selected_question.correct_answer,
            status=RoundQuestion.Status.PENDING,
            started_at=None,
            deadline=None,
        )
        round_q.participants.set(game.players.all())

    return round_obj


def start_round(round_obj, start_time=None):
    """Transition a pending round and its initial question to 'active' status with a 10s deadline."""
    if round_obj.game.status != Game.Status.ACTIVE:
        raise InvalidStateError("Cannot start round: associated game is not active.")

    if round_obj.status != Round.Status.PENDING:
        raise InvalidStateError(f"Cannot start round in '{round_obj.status}' status (must be pending).")

    current_q = round_obj.get_current_question()
    if current_q is None:
        raise RecordNotFoundError("Round has no question to activate.")

    now = start_time or timezone.now()
    deadline = now + timedelta(seconds=10)

    with transaction.atomic():
        round_obj.status = Round.Status.ACTIVE
        round_obj.save()

        current_q.status = RoundQuestion.Status.ACTIVE
        current_q.started_at = now
        current_q.deadline = deadline
        current_q.save()

    return round_obj


def submit_round_answer(round_obj, player, answer=None, option=None, current_time=None):
    """Submit an answer for the current active question of a round.

    Rules:
    - Trusted application time is captured immediately upon processing before deadline check.
    - Exactly on or after the deadline, the answer is rejected.
    - For Numeric questions: strictly integer inputs.
    - For Choice questions: AnswerOption instance or valid option ID belonging to current question.
    - Only participants of the active question may submit.
    - At most one accepted answer per player per question.
    """
    now = current_time or timezone.now()

    if round_obj.game.status != Game.Status.ACTIVE:
        raise InvalidStateError("Cannot submit answer: game is not active.")

    if round_obj.status != Round.Status.ACTIVE:
        raise InvalidStateError(f"Cannot submit answer: round is in '{round_obj.status}' status (must be active).")

    current_q = round_obj.get_current_question()
    if current_q is None or current_q.status != RoundQuestion.Status.ACTIVE:
        raise InvalidStateError("Cannot submit answer: no active question in this round.")

    if player.game_id != round_obj.game_id:
        raise InvalidInputError("Player does not belong to the game of this round.")

    if not current_q.participants.filter(id=player.id).exists():
        raise InvalidStateError("Player is not an active participant for the current question.")

    # Deadline boundary: exactly on deadline or after deadline is rejected
    if current_q.deadline is not None and now >= current_q.deadline:
        raise InvalidStateError("Answer rejected: question deadline has expired.")

    # Duplicate answer check
    if RoundAnswer.objects.filter(round_question=current_q, player=player).exists():
        raise InvalidStateError("Player has already submitted an accepted answer for this question.")

    if current_q.question_type == RoundQuestion.QuestionType.CHOICE:
        selected_option = option if option is not None else answer
        if isinstance(selected_option, int) and not isinstance(selected_option, bool):
            fetched = AnswerOption.objects.filter(id=selected_option).first()
            if fetched:
                selected_option = fetched

        if not isinstance(selected_option, AnswerOption):
            raise InvalidInputError("Answer for choice question must be an AnswerOption or valid option ID.")

        if selected_option.question_id != current_q.choice_question_id:
            raise InvalidInputError("Selected option does not belong to the current choice question.")

        with transaction.atomic():
            answer_obj = RoundAnswer.objects.create(
                round_question=current_q,
                player=player,
                selected_option=selected_option,
                is_correct=selected_option.is_correct,
                submitted_at=now,
            )
        return answer_obj

    else:
        # Numeric question
        if isinstance(answer, bool) or not isinstance(answer, int):
            raise InvalidInputError("Answer must strictly be an integer (floating point or non-integers are rejected).")

        diff = abs(answer - current_q.correct_answer)

        with transaction.atomic():
            answer_obj = RoundAnswer.objects.create(
                round_question=current_q,
                player=player,
                answer=answer,
                difference=diff,
                submitted_at=now,
            )
        return answer_obj


def _finalize_battle_completion(round_obj, winner, now, reason=None):
    """Atomically record battle completion, apply score/territory updates, and log capture (M08)."""
    target = round_obj.target_territory

    # Pre-check target owner:
    # "Преди прилагане на резултата проверете, че owner още съответства на битката."
    # "Ако целта вече не съответства на записаната битка, опитът за прилагане се отказва без частичен резултат или награда."
    if target is not None and target.owner_id != round_obj.defender_id:
        raise InvalidStateError("Target territory owner does not match the defender recorded for this battle.")

    with transaction.atomic():
        try:
            locked_round = Round.objects.select_for_update().get(id=round_obj.id)
            locked_target = Territory.objects.select_for_update().get(id=target.id) if target else None
            locked_attacker = Player.objects.select_for_update().get(id=round_obj.attacker_id) if round_obj.attacker else None
            locked_defender = Player.objects.select_for_update().get(id=round_obj.defender_id) if round_obj.defender else None
        except Exception:
            locked_round = Round.objects.get(id=round_obj.id)
            locked_target = Territory.objects.get(id=target.id) if target else None
            locked_attacker = Player.objects.get(id=round_obj.attacker_id) if round_obj.attacker else None
            locked_defender = Player.objects.get(id=round_obj.defender_id) if round_obj.defender else None

        # Idempotence: "Повторно приключване не повтаря нито една последица; само едно окончателно приключване носи награда, не всеки въпрос."
        if locked_round.status == Round.Status.COMPLETED:
            return locked_round

        if locked_target and locked_target.owner_id != locked_defender.id:
            raise InvalidStateError("Target territory owner does not match the defender recorded for this battle.")

        locked_round.winner = winner
        locked_round.status = Round.Status.COMPLETED
        locked_round.completed_at = now
        if reason:
            locked_round.completion_reason = reason
        elif winner is None and not locked_round.completion_reason:
            locked_round.completion_reason = "draw"

        if winner is not None:
            RoundPlacement.objects.create(round=locked_round, player=winner, place=1)

        # Apply consequences
        if locked_round.type == Round.Type.BATTLE:
            if winner == locked_attacker:
                p_before = locked_attacker.score
                t_before = locked_target.score

                locked_target.owner = locked_attacker
                locked_target.score += TERRITORY_SCORE_INCREMENT
                locked_target.save()

                total_reward = ROUND_VICTORY_REWARD + TERRITORY_CAPTURE_REWARD
                locked_attacker.score += total_reward
                locked_attacker.save()

                TerritoryCaptureLog.objects.create(
                    round=locked_round,
                    player=locked_attacker,
                    territory=locked_target,
                    points_awarded=total_reward,
                    player_score_before=p_before,
                    player_score_after=locked_attacker.score,
                    territory_score_before=t_before,
                    territory_score_after=locked_target.score,
                )
            elif winner == locked_defender:
                locked_defender.score += ROUND_VICTORY_REWARD
                locked_defender.save()

        elif locked_round.type == Round.Type.CAPITAL_ATTACK:
            if winner == locked_attacker:
                locked_attacker.score += ROUND_VICTORY_REWARD
                locked_attacker.save()
            elif winner == locked_defender:
                locked_defender.score += ROUND_VICTORY_REWARD
                locked_defender.save()

        locked_round.full_clean()
        locked_round.save()

    round_obj.refresh_from_db()
    return round_obj


def _finalize_round_completion(round_obj, now, reason=None):
    """Atomically record final round status, winner, victory reward, and territory capture rights (M07)."""
    first_p = round_obj.placements.filter(place=1).first()
    has_second = round_obj.placements.filter(place=2).exists()

    round_obj.winner = first_p.player if first_p else None
    round_obj.status = Round.Status.COMPLETED
    round_obj.completed_at = now
    if reason:
        round_obj.completion_reason = reason
    elif not has_second and not round_obj.completion_reason:
        round_obj.completion_reason = "unresolved_second_place: only one answer received"

    round_obj.full_clean()
    round_obj.save()

    # M07: Award victory reward and grant territory capture rights atomically
    if not round_obj.capture_rights.exists() and round_obj.type == Round.Type.CITY_CAPTURE:
        free_count = round_obj.game.territories.filter(owner__isnull=True).count()
        if round_obj.winner is not None:
            # 1. Victory reward for 1st place
            winner_player = round_obj.winner
            winner_player.score += ROUND_VICTORY_REWARD
            winner_player.save()

            # 2. Rights for 1st place based on available free territories:
            # 3 or more -> 2 rights
            # 2 -> 2 rights
            # 1 -> 1 right
            if free_count >= 2:
                p1_rights = 2
            elif free_count == 1:
                p1_rights = 1
            else:
                p1_rights = 0

            if p1_rights > 0:
                CaptureRight.objects.create(
                    round=round_obj,
                    player=winner_player,
                    order=1,
                    allowed_choices=p1_rights,
                    used_choices=0,
                )

            # 3. Rights for 2nd place (only if 3+ free territories AND 2nd place is determined)
            if free_count >= 3 and has_second:
                second_placement = round_obj.placements.filter(place=2).first()
                if second_placement:
                    CaptureRight.objects.create(
                        round=round_obj,
                        player=second_placement.player,
                        order=2,
                        allowed_choices=1,
                        used_choices=0,
                    )

    return round_obj


def resolve_round(round_obj, current_time=None, random_generator=None):
    """Evaluate answers, determine placements, trigger tie-breaker questions if needed, or complete round.

    Rules:
    - Allowed only when all question participants have answered OR when the 10s deadline has expired.
    - Proximity before speed: smaller absolute difference is better; for equal differences, earlier submitted_at wins.
    - Tie-breaking: exact ties in difference AND submit time for required places (1st or 2nd) trigger a new question
      for only the tied group (up to 3 questions max).
    - No answers: all participants are re-asked on a new question if limit/bank permits.
    - Final outcome: if bank exhausted or limit (3 questions) reached, unawarded places remain unfilled with reason.
    - In M07: Atomic finalization grants victory reward (+100) to winner and capture rights based on free territory count.
    - In M08: For battle / capital_attack rounds:
      * Choice question:
        - 1 correct answer: author wins immediately.
        - 2 correct answers: next question is an unused NumericQuestion for same 2 participants.
        - 0 correct answers: next question is an unused ChoiceQuestion for same 2 participants.
      * Numeric question:
        - Evaluates proximity and speed; exact ties advance to next NumericQuestion.
      * Limit is 3 questions max for round.
      * Idempotence: Repeated resolution of an already completed round repeats no consequences.
    """
    now = current_time or timezone.now()

    if round_obj.game.status != Game.Status.ACTIVE:
        raise InvalidStateError("Cannot resolve round: game is not active.")

    if round_obj.status != Round.Status.ACTIVE:
        raise InvalidStateError(f"Cannot resolve round: round is in '{round_obj.status}' status (must be active).")

    current_q = round_obj.get_current_question()
    if current_q is None:
        raise RecordNotFoundError("Round has no question to resolve.")

    # Check premature resolution
    participant_count = current_q.participants.count()
    answer_count = current_q.answers.count()
    all_answered = (answer_count >= participant_count and participant_count > 0)
    deadline_expired = (current_q.deadline is not None and now >= current_q.deadline)

    if not (all_answered or deadline_expired):
        raise InvalidStateError("Cannot resolve round before all participants have answered or deadline has expired.")

    # M08: Battle / Capital Attack resolution
    if round_obj.type in (Round.Type.BATTLE, Round.Type.CAPITAL_ATTACK):
        with transaction.atomic():
            try:
                locked_round = Round.objects.select_for_update().get(id=round_obj.id)
            except Exception:
                locked_round = Round.objects.get(id=round_obj.id)

            if locked_round.status == Round.Status.COMPLETED:
                return locked_round

            current_q.status = RoundQuestion.Status.COMPLETED
            current_q.save()

            if current_q.question_type == RoundQuestion.QuestionType.CHOICE:
                answers = list(current_q.answers.all())
                correct_answers = [a for a in answers if a.is_correct is True]

                if len(correct_answers) == 1:
                    winner = correct_answers[0].player
                    return _finalize_battle_completion(round_obj, winner, now)

                elif len(correct_answers) == 2:
                    # 2 correct answers: switch to NumericQuestion
                    if current_q.sequence >= 3:
                        return _finalize_battle_completion(round_obj, None, now, reason="limit_reached")

                    used_num_ids = RoundQuestion.objects.filter(
                        round__game=round_obj.game, question__isnull=False
                    ).values_list("question_id", flat=True)
                    avail_num = list(NumericQuestion.objects.exclude(id__in=used_num_ids))
                    if not avail_num:
                        return _finalize_battle_completion(round_obj, None, now, reason="question_bank_exhausted")

                    rng = random_generator or random
                    next_q = rng.choice(avail_num)
                    new_q = RoundQuestion.objects.create(
                        round=round_obj,
                        question_type=RoundQuestion.QuestionType.NUMERIC,
                        question=next_q,
                        sequence=current_q.sequence + 1,
                        question_text=next_q.text,
                        correct_answer=next_q.correct_answer,
                        status=RoundQuestion.Status.ACTIVE,
                        started_at=now,
                        deadline=now + timedelta(seconds=10),
                    )
                    new_q.participants.set([round_obj.attacker, round_obj.defender])
                    return round_obj

                else:
                    # 0 correct answers: switch to ChoiceQuestion
                    if current_q.sequence >= 3:
                        return _finalize_battle_completion(round_obj, None, now, reason="limit_reached")

                    used_choice_ids = RoundQuestion.objects.filter(
                        round__game=round_obj.game, choice_question__isnull=False
                    ).values_list("choice_question_id", flat=True)
                    avail_choice = list(
                        ChoiceQuestion.objects.exclude(id__in=used_choice_ids)
                        .annotate(
                            opt_count=models.Count("options"),
                            correct_count=models.Count("options", filter=models.Q(options__is_correct=True)),
                        )
                        .filter(opt_count=4, correct_count=1)
                    )
                    if not avail_choice:
                        return _finalize_battle_completion(round_obj, None, now, reason="question_bank_exhausted")

                    rng = random_generator or random
                    next_q = rng.choice(avail_choice)
                    new_q = RoundQuestion.objects.create(
                        round=round_obj,
                        question_type=RoundQuestion.QuestionType.CHOICE,
                        choice_question=next_q,
                        sequence=current_q.sequence + 1,
                        question_text=next_q.text,
                        correct_answer=None,
                        status=RoundQuestion.Status.ACTIVE,
                        started_at=now,
                        deadline=now + timedelta(seconds=10),
                    )
                    new_q.participants.set([round_obj.attacker, round_obj.defender])
                    return round_obj

            else:
                # Numeric Question in Battle
                answers = list(current_q.answers.order_by("difference", "submitted_at"))
                if len(answers) == 1:
                    return _finalize_battle_completion(round_obj, answers[0].player, now)
                elif len(answers) == 2:
                    a1, a2 = answers[0], answers[1]
                    if a1.difference < a2.difference:
                        return _finalize_battle_completion(round_obj, a1.player, now)
                    elif a1.difference == a2.difference:
                        if a1.submitted_at < a2.submitted_at:
                            return _finalize_battle_completion(round_obj, a1.player, now)
                        tied_players = [a1.player, a2.player]
                    else:
                        return _finalize_battle_completion(round_obj, a2.player, now)
                else:
                    tied_players = [round_obj.attacker, round_obj.defender]

                if current_q.sequence >= 3:
                    return _finalize_battle_completion(round_obj, None, now, reason="limit_reached")

                used_num_ids = RoundQuestion.objects.filter(
                    round__game=round_obj.game, question__isnull=False
                ).values_list("question_id", flat=True)
                avail_num = list(NumericQuestion.objects.exclude(id__in=used_num_ids))
                if not avail_num:
                    return _finalize_battle_completion(round_obj, None, now, reason="question_bank_exhausted")

                rng = random_generator or random
                next_q = rng.choice(avail_num)
                new_q = RoundQuestion.objects.create(
                    round=round_obj,
                    question_type=RoundQuestion.QuestionType.NUMERIC,
                    question=next_q,
                    sequence=current_q.sequence + 1,
                    question_text=next_q.text,
                    correct_answer=next_q.correct_answer,
                    status=RoundQuestion.Status.ACTIVE,
                    started_at=now,
                    deadline=now + timedelta(seconds=10),
                )
                new_q.participants.set(tied_players)
                return round_obj

    # M06 / M07: CITY_CAPTURE Resolution
    with transaction.atomic():
        # Complete the current question
        current_q.status = RoundQuestion.Status.COMPLETED
        current_q.save()

        # Check existing placements
        has_first = round_obj.placements.filter(place=1).exists()
        has_second = round_obj.placements.filter(place=2).exists()

        answers = list(current_q.answers.order_by("difference", "submitted_at"))

        # Group answers by (difference, submitted_at)
        groups = []
        for key, grp in itertools.groupby(answers, key=lambda a: (a.difference, a.submitted_at)):
            groups.append(list(grp))

        tied_players = []

        if not has_first:
            # Resolving 1st (and potentially 2nd) place
            if len(answers) == 0:
                tied_players = list(current_q.participants.all())
            elif len(answers) == 1:
                RoundPlacement.objects.create(round=round_obj, player=answers[0].player, place=1)
                has_first = True
            else:
                if len(groups[0]) == 1:
                    p1 = groups[0][0].player
                    RoundPlacement.objects.create(round=round_obj, player=p1, place=1)
                    has_first = True

                    if len(groups) > 1:
                        if len(groups[1]) == 1:
                            p2 = groups[1][0].player
                            RoundPlacement.objects.create(round=round_obj, player=p2, place=2)
                            has_second = True
                        else:
                            tied_players = [a.player for a in groups[1]]
                else:
                    tied_players = [a.player for a in groups[0]]

        elif has_first and not has_second:
            # Resolving 2nd place
            if len(answers) == 0:
                tied_players = list(current_q.participants.all())
            elif len(answers) == 1:
                p2 = answers[0].player
                RoundPlacement.objects.create(round=round_obj, player=p2, place=2)
                has_second = True
            else:
                if len(groups[0]) == 1:
                    p2 = groups[0][0].player
                    RoundPlacement.objects.create(round=round_obj, player=p2, place=2)
                    has_second = True
                else:
                    tied_players = [a.player for a in groups[0]]

        # Determine if we can finish or need another question
        # If free territories are 1 or 2, 2nd place is not required to have rights
        free_count = round_obj.game.territories.filter(owner__isnull=True).count()
        only_first_needed = (free_count in (1, 2))

        is_fully_resolved = (
            (has_first and has_second)
            or (has_first and only_first_needed)
            or (has_first and len(tied_players) == 0)
        )

        if is_fully_resolved:
            return _finalize_round_completion(round_obj, now)

        # Ties remain: check limit (max 3 questions) and bank availability
        used_q_ids = RoundQuestion.objects.filter(
            round__game=round_obj.game, question__isnull=False
        ).values_list("question_id", flat=True)
        available_questions = list(NumericQuestion.objects.exclude(id__in=used_q_ids))

        if current_q.sequence >= 3:
            return _finalize_round_completion(round_obj, now, reason="limit_reached")

        if not available_questions:
            return _finalize_round_completion(round_obj, now, reason="question_bank_exhausted")

        # Activate tie-breaker question atomically
        rng = random_generator or random
        next_q = rng.choice(available_questions)
        new_sequence = current_q.sequence + 1

        new_round_q = RoundQuestion.objects.create(
            round=round_obj,
            question_type=RoundQuestion.QuestionType.NUMERIC,
            question=next_q,
            sequence=new_sequence,
            question_text=next_q.text,
            correct_answer=next_q.correct_answer,
            status=RoundQuestion.Status.ACTIVE,
            started_at=now,
            deadline=now + timedelta(seconds=10),
        )
        new_round_q.participants.set(tied_players)

    return round_obj


# ==============================================================================
# M07 — Territory Capture and Scoring
# ==============================================================================

def get_eligible_territories(game, player):
    """Return queryset of free territories eligible for capture by the given player.

    Rules:
    - Must be free (owner is None).
    - Must belong to the game.
    - Adjacent to at least one currently owned territory of the player (capital territory is also owned).
    - Exception: If NO free territories are adjacent to ANY of player's owned holdings,
      player may choose ANY free territory in the game.
    """
    free_territories = game.territories.filter(owner__isnull=True)
    if not free_territories.exists():
        return free_territories.none()

    owned_territories = game.territories.filter(owner=player)
    adjacent_free = free_territories.filter(neighbors__in=owned_territories).distinct()

    if adjacent_free.exists():
        return adjacent_free

    # Fallback exception: if no adjacent free territory exists, any free territory is allowed
    return free_territories


def choose_territory_capture(round_obj, player, territory):
    """Execute a territory capture choice by an authorized player.

    Rules:
    - Game must be active.
    - Round must be completed.
    - Must be from the latest completed city_capture round.
    - Player must have unexhausted capture rights in this round.
    - Turn order enforced: 1st place must finish choosing before 2nd place can choose.
    - Territory must be free, belong to this game, and be eligible (adjacent or fallback).
    - Atomically: change owner, increase territory score by 100, award 200 points to player,
      consume 1 choice, record capture log.
    """
    if round_obj.game.status != Game.Status.ACTIVE:
        raise InvalidStateError("Cannot choose territory: game is not active.")

    if round_obj.status != Round.Status.COMPLETED:
        raise InvalidStateError("Cannot choose territory: round must be completed.")

    latest_round = round_obj.game.rounds.filter(
        type=Round.Type.CITY_CAPTURE,
        status=Round.Status.COMPLETED,
    ).order_by("-number").first()
    if latest_round is None or round_obj.id != latest_round.id:
        raise InvalidStateError("Territory choices can only be made from the latest completed city_capture round.")

    right = round_obj.capture_rights.filter(player=player).first()
    if right is None:
        raise InvalidInputError("Player has no territory capture rights in this round.")

    if right.used_choices >= right.allowed_choices:
        raise InvalidStateError("Player has already used all allowed territory choices.")

    # Check turn order: if order == 2, order 1 must be fulfilled or no free territories left
    if right.order == 2:
        order1_right = round_obj.capture_rights.filter(order=1).first()
        if order1_right and order1_right.used_choices < order1_right.allowed_choices:
            if round_obj.game.territories.filter(owner__isnull=True).exists():
                raise InvalidStateError("Cannot choose out of turn: first place player must finish choosing first.")

    # Territory checks
    if territory.game_id != round_obj.game_id:
        raise InvalidInputError("Territory belongs to a different game.")

    if territory.owner is not None:
        raise InvalidInputError(f"Territory '{territory.name}' is already owned by {territory.owner}.")

    eligible_territories = get_eligible_territories(round_obj.game, player)
    if not eligible_territories.filter(id=territory.id).exists():
        raise InvalidInputError(f"Territory '{territory.name}' is not eligible for capture by this player.")

    with transaction.atomic():
        try:
            locked_territory = Territory.objects.select_for_update().get(id=territory.id)
            locked_player = Player.objects.select_for_update().get(id=player.id)
            locked_right = CaptureRight.objects.select_for_update().get(id=right.id)
        except Exception:
            locked_territory = Territory.objects.get(id=territory.id)
            locked_player = Player.objects.get(id=player.id)
            locked_right = CaptureRight.objects.get(id=right.id)

        # Re-check under lock (concurrency protection)
        if locked_territory.owner is not None:
            raise InvalidInputError(f"Territory '{locked_territory.name}' was already captured.")
        if locked_right.used_choices >= locked_right.allowed_choices:
            raise InvalidStateError("Player has already used all allowed territory choices.")

        # Scores before
        p_before = locked_player.score
        t_before = locked_territory.score

        # Update territory
        locked_territory.owner = locked_player
        locked_territory.score += TERRITORY_SCORE_INCREMENT
        locked_territory.save()

        # Update player score
        locked_player.score += TERRITORY_CAPTURE_REWARD
        locked_player.save()

        # Consume 1 choice
        locked_right.used_choices += 1
        locked_right.save()

        # Record audit log
        TerritoryCaptureLog.objects.create(
            round=round_obj,
            player=locked_player,
            territory=locked_territory,
            points_awarded=TERRITORY_CAPTURE_REWARD,
            player_score_before=p_before,
            player_score_after=locked_player.score,
            territory_score_before=t_before,
            territory_score_after=locked_territory.score,
        )

    locked_territory.refresh_from_db()
    locked_player.refresh_from_db()
    return locked_territory, locked_player
