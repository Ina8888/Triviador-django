"""Comprehensive test suite for M08 — Battles and Capital Attacks."""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from games.exceptions import InvalidInputError, InvalidStateError, RecordNotFoundError
from games.models import (
    Capital,
    Game,
    Player,
    Round,
    RoundAnswer,
    RoundPlacement,
    RoundQuestion,
    Territory,
    TerritoryCaptureLog,
)
from games.services import (
    ROUND_VICTORY_REWARD,
    TERRITORY_CAPTURE_REWARD,
    TERRITORY_SCORE_INCREMENT,
    create_round,
    initialize_game,
    resolve_round,
    start_round,
    submit_round_answer,
)
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion

User = get_user_model()


class BattlesTestCase(TestCase):
    """Test suite covering M08 rules, target validation, answer rules, battles, capital attacks, and concurrency."""

    def setUp(self):
        self.category = Category.objects.create(name="История")

        # Bank of Choice questions
        self.choice_questions = []
        for i in range(1, 15):
            q = ChoiceQuestion.objects.create(
                category=self.category,
                text=f"Choice Question {i}?",
            )
            for j in range(1, 5):
                AnswerOption.objects.create(
                    question=q,
                    text=f"Option {j} for Q{i}",
                    is_correct=(j == 1),
                )
            self.choice_questions.append(q)

        # Bank of Numeric questions
        self.numeric_questions = [
            NumericQuestion.objects.create(
                category=self.category,
                text=f"Numeric Question {i}?",
                correct_answer=100 * i,
            )
            for i in range(1, 15)
        ]

        # Game and 3 players
        self.game = Game.objects.create(status=Game.Status.WAITING)
        self.u1 = User.objects.create_user(username="b_u1", email="b_u1@example.com", password="pass")
        self.u2 = User.objects.create_user(username="b_u2", email="b_u2@example.com", password="pass")
        self.u3 = User.objects.create_user(username="b_u3", email="b_u3@example.com", password="pass")

        self.p1 = Player.objects.create(user=self.u1, game=self.game, color=Player.Color.RED)
        self.p2 = Player.objects.create(user=self.u2, game=self.game, color=Player.Color.GREEN)
        self.p3 = Player.objects.create(user=self.u3, game=self.game, color=Player.Color.BLUE)

        # Initialize game (creates 18 territories, 3 capitals)
        initialize_game(self.game)

    def _fully_capture_map(self):
        """Helper: distribute remaining 15 neutral territories among players so 0 free remain."""
        free_territories = list(self.game.territories.filter(owner__isnull=True).order_by("id"))
        for i, t in enumerate(free_territories):
            if i % 3 == 0:
                t.owner = self.p1
            elif i % 3 == 1:
                t.owner = self.p2
            else:
                t.owner = self.p3
            t.score = 100
            t.save()

    def _get_adjacent_target(self, attacker, defender=None, is_capital=False):
        """Find an enemy territory adjacent to attacker, optionally owned by defender and matching capital flag."""
        if is_capital:
            if defender is not None:
                cap = Capital.objects.get(player=defender)
            else:
                cap = Capital.objects.exclude(player=attacker).first()
            # Ensure at least one neighbor of cap.territory is owned by attacker
            n = cap.territory.neighbors.exclude(capital__isnull=False).first()
            if n:
                n.owner = attacker
                n.save()
            return cap.territory

        attacker_holdings = self.game.territories.filter(owner=attacker)
        qs = self.game.territories.filter(
            neighbors__in=attacker_holdings
        ).exclude(owner=attacker).filter(capital__isnull=True).distinct()

        if defender is not None:
            qs = qs.filter(owner=defender)

        target = qs.first()
        self.assertIsNotNone(target, f"Failed to find adjacent target for attacker {attacker}")
        return target

    def _get_non_adjacent_target(self, attacker):
        """Find an enemy territory NOT adjacent to any of attacker's holdings."""
        attacker_holdings = self.game.territories.filter(owner=attacker)
        adjacent_ids = self.game.territories.filter(
            neighbors__in=attacker_holdings
        ).values_list("id", flat=True)

        target = self.game.territories.exclude(id__in=adjacent_ids).exclude(owner=attacker).first()
        self.assertIsNotNone(target, "Failed to find non-adjacent target")
        return target

    def _get_options(self, choice_q):
        correct = choice_q.options.get(is_correct=True)
        incorrect = choice_q.options.filter(is_correct=False).first()
        return correct, incorrect

    # ==============================================================================
    # 1. Target Validation Tests
    # ==============================================================================

    def test_target_validation_blocks_when_free_territories_remain(self):
        """Cannot start battles before all territories on map are captured."""
        target = self._get_adjacent_target(self.p1)
        with self.assertRaises(InvalidStateError):
            create_round(self.game, attacker=self.p1, target_territory=target)

    def test_target_validation_own_territory_rejected(self):
        """Attacker cannot target their own territory."""
        self._fully_capture_map()
        own_territory = self.game.territories.filter(owner=self.p1).first()
        with self.assertRaises(InvalidInputError):
            create_round(self.game, attacker=self.p1, target_territory=own_territory)

    def test_target_validation_free_territory_rejected(self):
        """Target territory cannot be free."""
        # Uncaptured territory
        free_territory = self.game.territories.filter(owner__isnull=True).first()
        with self.assertRaises(InvalidStateError):  # Fails map check or territory check
            create_round(self.game, attacker=self.p1, target_territory=free_territory)

    def test_target_validation_non_adjacent_territory_rejected(self):
        """Target territory must be adjacent to attacker; M07 free exception does NOT apply to battles."""
        self._fully_capture_map()
        non_adjacent = self._get_non_adjacent_target(self.p1)
        with self.assertRaises(InvalidInputError):
            create_round(self.game, attacker=self.p1, target_territory=non_adjacent)

    def test_target_validation_foreign_game_territory_rejected(self):
        """Target territory belonging to another game is rejected."""
        self._fully_capture_map()
        other_game = Game.objects.create(status=Game.Status.WAITING)
        other_t = Territory.objects.create(game=other_game, name="Foreign", slug="foreign", score=100)
        with self.assertRaises(InvalidInputError):
            create_round(self.game, attacker=self.p1, target_territory=other_t)

    def test_target_validation_mismatched_defender_rejected(self):
        """Specifying a defender different from target.owner is rejected."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        with self.assertRaises(InvalidInputError):
            create_round(self.game, attacker=self.p1, target_territory=target, defender=self.p3)

    def test_automatic_round_type_detection(self):
        """Ordinary territory sets BATTLE; capital sets CAPITAL_ATTACK."""
        self._fully_capture_map()

        # 1. Ordinary target
        ordinary_target = self._get_adjacent_target(self.p1, is_capital=False)
        round_battle = create_round(self.game, attacker=self.p1, target_territory=ordinary_target)
        self.assertEqual(round_battle.type, Round.Type.BATTLE)
        self.assertEqual(round_battle.defender, ordinary_target.owner)
        round_battle.status = Round.Status.COMPLETED
        round_battle.completed_at = timezone.now()
        round_battle.completion_reason = "test"
        round_battle.save()

        # 2. Capital target
        # Ensure p2 has a capital adjacent to p1
        cap_target = self._get_adjacent_target(self.p1, is_capital=True)
        round_cap = create_round(self.game, attacker=self.p1, target_territory=cap_target)
        self.assertEqual(round_cap.type, Round.Type.CAPITAL_ATTACK)
        self.assertEqual(round_cap.defender, cap_target.owner)

    # ==============================================================================
    # 2. Participant and Answer Validation Tests
    # ==============================================================================

    def test_participant_validation_third_player_excluded(self):
        """The 3rd player in the game is not a participant and cannot answer."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        self.assertEqual(set(current_q.participants.all()), {self.p1, self.p2})
        self.assertNotIn(self.p3, current_q.participants.all())

        # Attempt answer by p3
        correct_opt, _ = self._get_options(current_q.choice_question)
        with self.assertRaises(InvalidStateError):
            submit_round_answer(round_obj, self.p3, option=correct_opt)

    def test_answer_validation_option_from_another_question_rejected(self):
        """Submitting an option from another ChoiceQuestion is rejected."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        # Grab option from a different question
        other_q = self.choice_questions[5]
        foreign_opt = other_q.options.first()

        with self.assertRaises(InvalidInputError):
            submit_round_answer(round_obj, self.p1, option=foreign_opt)

    def test_answer_validation_duplicate_answer_rejected(self):
        """Submitting an answer twice for the same question is rejected."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        correct_opt, _ = self._get_options(current_q.choice_question)

        submit_round_answer(round_obj, self.p1, option=correct_opt)
        with self.assertRaises(InvalidStateError):
            submit_round_answer(round_obj, self.p1, option=correct_opt)

    def test_answer_validation_expired_deadline_rejected(self):
        """Submitting on or after deadline is rejected."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        start_time = timezone.now()
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=start_time)

        current_q = round_obj.get_current_question()
        correct_opt, _ = self._get_options(current_q.choice_question)

        # After 10s deadline
        expired_time = start_time + timedelta(seconds=10)
        with self.assertRaises(InvalidStateError):
            submit_round_answer(round_obj, self.p1, option=correct_opt, current_time=expired_time)

    # ==============================================================================
    # 3. Battle Outcomes and Scoring Tests
    # ==============================================================================

    def test_battle_one_correct_attacker_wins(self):
        """One correct answer by attacker: attacker wins territory, score increases, awards +300 points."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2, is_capital=False)
        original_score = target.score
        p1_orig = self.p1.score
        p2_orig = self.p2.score

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        correct_opt, incorrect_opt = self._get_options(current_q.choice_question)

        submit_round_answer(round_obj, self.p1, option=correct_opt)
        submit_round_answer(round_obj, self.p2, option=incorrect_opt)

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        target.refresh_from_db()
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()

        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p1)
        self.assertEqual(target.owner, self.p1)
        self.assertEqual(target.score, original_score + TERRITORY_SCORE_INCREMENT)
        self.assertEqual(self.p1.score, p1_orig + ROUND_VICTORY_REWARD + TERRITORY_CAPTURE_REWARD)
        self.assertEqual(self.p2.score, p2_orig)

        # Verify TerritoryCaptureLog audit entry
        log_entry = TerritoryCaptureLog.objects.filter(round=round_obj).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.player, self.p1)
        self.assertEqual(log_entry.territory, target)
        self.assertEqual(log_entry.points_awarded, ROUND_VICTORY_REWARD + TERRITORY_CAPTURE_REWARD)
        self.assertEqual(log_entry.territory_score_after, target.score)

    def test_battle_one_correct_defender_wins(self):
        """One correct answer by defender: territory unchanged, defender gets +100 points."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2, is_capital=False)
        original_score = target.score
        p1_orig = self.p1.score
        p2_orig = self.p2.score

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        correct_opt, incorrect_opt = self._get_options(current_q.choice_question)

        submit_round_answer(round_obj, self.p1, option=incorrect_opt)
        submit_round_answer(round_obj, self.p2, option=correct_opt)

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        target.refresh_from_db()
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()

        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p2)
        self.assertEqual(target.owner, self.p2)  # Unchanged
        self.assertEqual(target.score, original_score)  # Unchanged
        self.assertEqual(self.p2.score, p2_orig + ROUND_VICTORY_REWARD)
        self.assertEqual(self.p1.score, p1_orig)

    def test_battle_two_correct_switches_to_numeric_question(self):
        """Two correct answers: speed is NOT compared; round advances to NumericQuestion."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        start_time = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=start_time)

        current_q = round_obj.get_current_question()
        correct_opt, _ = self._get_options(current_q.choice_question)

        # p1 answers earlier than p2
        submit_round_answer(round_obj, self.p1, option=correct_opt, current_time=start_time + timedelta(seconds=1))
        submit_round_answer(round_obj, self.p2, option=correct_opt, current_time=start_time + timedelta(seconds=4))

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.ACTIVE)
        self.assertIsNone(round_obj.winner)

        # Verify next question is numeric
        next_q = round_obj.get_current_question()
        self.assertEqual(next_q.sequence, 2)
        self.assertEqual(next_q.question_type, RoundQuestion.QuestionType.NUMERIC)
        self.assertIsNotNone(next_q.question)
        self.assertEqual(next_q.status, RoundQuestion.Status.ACTIVE)
        self.assertEqual(set(next_q.participants.all()), {self.p1, self.p2})

    def test_battle_zero_correct_switches_to_choice_question(self):
        """Zero correct answers: round advances to a new ChoiceQuestion."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        start_time = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=start_time)

        current_q = round_obj.get_current_question()
        _, incorrect_opt = self._get_options(current_q.choice_question)

        # Both incorrect
        submit_round_answer(round_obj, self.p1, option=incorrect_opt, current_time=start_time + timedelta(seconds=1))
        submit_round_answer(round_obj, self.p2, option=incorrect_opt, current_time=start_time + timedelta(seconds=2))

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.ACTIVE)
        next_q = round_obj.get_current_question()
        self.assertEqual(next_q.sequence, 2)
        self.assertEqual(next_q.question_type, RoundQuestion.QuestionType.CHOICE)

    # ==============================================================================
    # 4. Capital Attack Outcomes
    # ==============================================================================

    def test_capital_attack_attacker_wins_preserves_capital(self):
        """Attacker wins capital_attack: awards +100 victory, capital health/owner/player unchanged."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2, is_capital=True)
        capital = target.capital
        self.assertEqual(capital.health, 3)

        p1_orig = self.p1.score
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        correct_opt, incorrect_opt = self._get_options(current_q.choice_question)

        submit_round_answer(round_obj, self.p1, option=correct_opt)
        submit_round_answer(round_obj, self.p2, option=incorrect_opt)

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        target.refresh_from_db()
        capital.refresh_from_db()
        self.p1.refresh_from_db()

        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p1)
        self.assertEqual(self.p1.score, p1_orig + ROUND_VICTORY_REWARD)

        # Capital and territory unchanged
        self.assertEqual(target.owner, self.p2)
        self.assertEqual(capital.health, 3)
        self.assertEqual(capital.player, self.p2)

    def test_capital_attack_defender_wins_preserves_capital(self):
        """Defender wins capital_attack: awards +100 victory, capital health/owner/player unchanged."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2, is_capital=True)
        capital = target.capital
        p2_orig = self.p2.score

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        current_q = round_obj.get_current_question()
        correct_opt, incorrect_opt = self._get_options(current_q.choice_question)

        submit_round_answer(round_obj, self.p1, option=incorrect_opt)
        submit_round_answer(round_obj, self.p2, option=correct_opt)

        resolve_round(round_obj)

        round_obj.refresh_from_db()
        capital.refresh_from_db()
        self.p2.refresh_from_db()

        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p2)
        self.assertEqual(self.p2.score, p2_orig + ROUND_VICTORY_REWARD)
        self.assertEqual(capital.health, 3)

    # ==============================================================================
    # 5. Question Sequence and Limits
    # ==============================================================================

    def test_numeric_tie_breaker_proximity_and_speed(self):
        """Numeric question evaluates proximity, then speed."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        start_time = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=start_time)

        # Step 1: Both correct -> switches to numeric
        c_q = round_obj.get_current_question()
        c_opt, _ = self._get_options(c_q.choice_question)
        submit_round_answer(round_obj, self.p1, option=c_opt, current_time=start_time + timedelta(seconds=1))
        submit_round_answer(round_obj, self.p2, option=c_opt, current_time=start_time + timedelta(seconds=2))
        resolve_round(round_obj)

        # Step 2: Numeric question (sequence 2)
        num_q = round_obj.get_current_question()
        self.assertEqual(num_q.sequence, 2)
        self.assertEqual(num_q.question_type, RoundQuestion.QuestionType.NUMERIC)

        # p1 gives exact answer, p2 gives answer off by 10
        t2 = start_time + timedelta(seconds=5)
        submit_round_answer(round_obj, self.p1, answer=num_q.correct_answer, current_time=t2)
        submit_round_answer(round_obj, self.p2, answer=num_q.correct_answer + 10, current_time=t2)

        resolve_round(round_obj, current_time=t2 + timedelta(seconds=1))

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p1)

    def test_round_question_limit_reached_on_third_question(self):
        """Reaching max 3 questions without a winner completes round with reason='limit_reached'."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        t = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=t)

        # Q1: 0 correct -> Q2
        q1 = round_obj.get_current_question()
        _, inc = self._get_options(q1.choice_question)
        submit_round_answer(round_obj, self.p1, option=inc, current_time=t + timedelta(seconds=1))
        submit_round_answer(round_obj, self.p2, option=inc, current_time=t + timedelta(seconds=2))
        resolve_round(round_obj)

        # Q2: 0 correct -> Q3
        q2 = round_obj.get_current_question()
        _, inc2 = self._get_options(q2.choice_question)
        submit_round_answer(round_obj, self.p1, option=inc2, current_time=t + timedelta(seconds=3))
        submit_round_answer(round_obj, self.p2, option=inc2, current_time=t + timedelta(seconds=4))
        resolve_round(round_obj)

        # Q3: 0 correct -> limit reached!
        q3 = round_obj.get_current_question()
        self.assertEqual(q3.sequence, 3)
        _, inc3 = self._get_options(q3.choice_question)
        submit_round_answer(round_obj, self.p1, option=inc3, current_time=t + timedelta(seconds=5))
        submit_round_answer(round_obj, self.p2, option=inc3, current_time=t + timedelta(seconds=6))
        resolve_round(round_obj)

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertIsNone(round_obj.winner)
        self.assertEqual(round_obj.completion_reason, "limit_reached")
        self.assertEqual(round_obj.questions.count(), 3)

    def test_winner_determined_on_third_question_accepted_without_fourth(self):
        """Winner determined on 3rd question is accepted and no 4th question is created."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        t = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=t)

        # Q1: 0 correct -> Q2
        q1 = round_obj.get_current_question()
        _, inc = self._get_options(q1.choice_question)
        submit_round_answer(round_obj, self.p1, option=inc, current_time=t + timedelta(seconds=1))
        submit_round_answer(round_obj, self.p2, option=inc, current_time=t + timedelta(seconds=2))
        resolve_round(round_obj)

        # Q2: 0 correct -> Q3
        q2 = round_obj.get_current_question()
        _, inc2 = self._get_options(q2.choice_question)
        submit_round_answer(round_obj, self.p1, option=inc2, current_time=t + timedelta(seconds=3))
        submit_round_answer(round_obj, self.p2, option=inc2, current_time=t + timedelta(seconds=4))
        resolve_round(round_obj)

        # Q3: p1 correct -> p1 wins!
        q3 = round_obj.get_current_question()
        cor3, inc3 = self._get_options(q3.choice_question)
        submit_round_answer(round_obj, self.p1, option=cor3, current_time=t + timedelta(seconds=5))
        submit_round_answer(round_obj, self.p2, option=inc3, current_time=t + timedelta(seconds=6))
        resolve_round(round_obj)

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.p1)
        self.assertEqual(round_obj.questions.count(), 3)

    def test_missing_initial_question_aborts_creation(self):
        """Lack of available ChoiceQuestion in bank aborts create_round without DB changes."""
        self._fully_capture_map()
        ChoiceQuestion.objects.all().delete()
        target = self._get_adjacent_target(self.p1, defender=self.p2)

        rounds_before = Round.objects.count()
        with self.assertRaises(RecordNotFoundError):
            create_round(self.game, attacker=self.p1, target_territory=target)
        self.assertEqual(Round.objects.count(), rounds_before)

    # ==============================================================================
    # 6. Data Integrity and Disambiguation
    # ==============================================================================

    def test_same_ids_in_different_question_models_disambiguated(self):
        """ChoiceQuestion and NumericQuestion sharing identical ID=999 remain distinct and unambiguous."""
        self._fully_capture_map()
        cat = self.category

        # Create both with id=999
        cq = ChoiceQuestion.objects.create(id=999, category=cat, text="Shared ID Choice?")
        for j in range(1, 5):
            AnswerOption.objects.create(question=cq, text=f"Opt {j}", is_correct=(j == 1))

        nq = NumericQuestion.objects.create(id=999, category=cat, text="Shared ID Numeric?", correct_answer=999)

        target = self._get_adjacent_target(self.p1, defender=self.p2)
        round_obj = create_round(self.game, attacker=self.p1, target_territory=target, question=cq)
        start_round(round_obj)

        rq1 = round_obj.get_current_question()
        self.assertEqual(rq1.choice_question_id, 999)
        self.assertIsNone(rq1.question_id)
        self.assertEqual(rq1.question_type, RoundQuestion.QuestionType.CHOICE)

        # Force next question to be the numeric question with id=999
        c_opt, _ = self._get_options(cq)
        t = timezone.now()
        submit_round_answer(round_obj, self.p1, option=c_opt, current_time=t)
        submit_round_answer(round_obj, self.p2, option=c_opt, current_time=t + timedelta(seconds=1))

        # We resolve round with our specific numeric question
        resolve_round(round_obj, random_generator=type("Rng", (), {"choice": lambda self, lst: nq})())

        round_obj.refresh_from_db()
        rq2 = round_obj.get_current_question()
        self.assertEqual(rq2.sequence, 2)
        self.assertEqual(rq2.question_type, RoundQuestion.QuestionType.NUMERIC)
        self.assertEqual(rq2.question_id, 999)
        self.assertIsNone(rq2.choice_question_id)

    def test_history_reconstruction_without_data_loss(self):
        """Sequence of Choice followed by Numeric preserves all history and distinct answer structures."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)
        t = timezone.now()

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj, start_time=t)

        # Choice question
        q1 = round_obj.get_current_question()
        cor1, _ = self._get_options(q1.choice_question)
        ans1_p1 = submit_round_answer(round_obj, self.p1, option=cor1, current_time=t)
        ans1_p2 = submit_round_answer(round_obj, self.p2, option=cor1, current_time=t + timedelta(seconds=1))

        resolve_round(round_obj)

        # Numeric question
        q2 = round_obj.get_current_question()
        t2 = t + timedelta(seconds=5)
        ans2_p1 = submit_round_answer(round_obj, self.p1, answer=q2.correct_answer, current_time=t2)
        ans2_p2 = submit_round_answer(round_obj, self.p2, answer=q2.correct_answer + 5, current_time=t2 + timedelta(seconds=1))

        resolve_round(round_obj, current_time=t2 + timedelta(seconds=2))

        # Reconstruct and assert
        round_obj.refresh_from_db()
        questions = list(round_obj.questions.order_by("sequence"))
        self.assertEqual(len(questions), 2)

        # Question 1 verification
        self.assertEqual(questions[0].question_type, RoundQuestion.QuestionType.CHOICE)
        q1_answers = list(questions[0].answers.order_by("submitted_at"))
        self.assertEqual(len(q1_answers), 2)
        self.assertEqual(q1_answers[0].selected_option, cor1)
        self.assertTrue(q1_answers[0].is_correct)
        self.assertIsNone(q1_answers[0].answer)

        # Question 2 verification
        self.assertEqual(questions[1].question_type, RoundQuestion.QuestionType.NUMERIC)
        q2_answers = list(questions[1].answers.order_by("difference"))
        self.assertEqual(len(q2_answers), 2)
        self.assertEqual(q2_answers[0].answer, q2.correct_answer)
        self.assertEqual(q2_answers[0].difference, 0)
        self.assertIsNone(q2_answers[0].selected_option)

    # ==============================================================================
    # 7. Robustness and Concurrency
    # ==============================================================================

    def test_target_owner_mismatch_at_resolution_aborts_without_reward(self):
        """If target owner changed before resolve_round, operation aborts with InvalidStateError and preserves answers."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        q = round_obj.get_current_question()
        cor, _ = self._get_options(q.choice_question)
        submit_round_answer(round_obj, self.p1, option=cor)

        # Simulate out-of-band change to target owner before resolve
        target.owner = self.p3
        target.save()

        p1_score_before = self.p1.score
        with self.assertRaises(InvalidStateError):
            resolve_round(round_obj, current_time=timezone.now() + timedelta(seconds=11))

        # Answers still exist
        self.assertEqual(q.answers.count(), 1)
        # Score unchanged
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.score, p1_score_before)

    def test_idempotent_repeated_resolution(self):
        """Repeated resolution of an already completed round is rejected and causes no duplicate scoring."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        q = round_obj.get_current_question()
        cor, inc = self._get_options(q.choice_question)
        submit_round_answer(round_obj, self.p1, option=cor)
        submit_round_answer(round_obj, self.p2, option=inc)

        resolve_round(round_obj)
        self.p1.refresh_from_db()
        p1_score_after_first = self.p1.score

        # Second resolution is rejected with InvalidStateError and repeats no consequences
        with self.assertRaises(InvalidStateError):
            resolve_round(round_obj)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.score, p1_score_after_first)
        self.assertEqual(TerritoryCaptureLog.objects.filter(round=round_obj).count(), 1)

    def test_concurrency_locking_prevents_duplicate_next_question(self):
        """Simulate concurrent resolution on tie: unique constraint prevents duplicate next question."""
        self._fully_capture_map()
        target = self._get_adjacent_target(self.p1, defender=self.p2)

        round_obj = create_round(self.game, attacker=self.p1, target_territory=target)
        start_round(round_obj)

        q = round_obj.get_current_question()
        cor, _ = self._get_options(q.choice_question)
        submit_round_answer(round_obj, self.p1, option=cor)
        submit_round_answer(round_obj, self.p2, option=cor)

        # First resolve creates sequence 2
        resolve_round(round_obj)
        self.assertEqual(round_obj.questions.count(), 2)

        # An attempt to create another sequence=2 on the same round violates unique constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoundQuestion.objects.create(
                    round=round_obj,
                    sequence=2,
                    question_type=RoundQuestion.QuestionType.NUMERIC,
                    question_text="Duplicate Seq",
                    correct_answer=123,
                )
