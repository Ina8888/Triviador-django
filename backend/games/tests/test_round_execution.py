from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from games.exceptions import InvalidInputError, InvalidStateError, RecordNotFoundError
from games.models import Game, Player, Round, RoundAnswer, RoundPlacement, RoundQuestion
from games.services import create_round, resolve_round, start_round, submit_round_answer
from questions.models import Category, NumericQuestion

User = get_user_model()


class RoundExecutionTests(TestCase):
    """Comprehensive test suite for M06 — Rounds."""

    def setUp(self):
        # 1. Create category and numeric questions
        self.category = Category.objects.create(name="История")
        self.q1 = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е основана българската държава?",
            correct_answer=681,
        )
        self.q2 = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е обявена независимостта на България?",
            correct_answer=1908,
        )
        self.q3 = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е въведено християнството в България?",
            correct_answer=864,
        )
        self.q4 = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година избухва Априлското въстание?",
            correct_answer=1876,
        )

        # 2. Create an active game with exactly 3 players
        self.game = Game.objects.create(status=Game.Status.ACTIVE)
        self.user1 = User.objects.create_user(username="m6_u1", email="m6_u1@example.com", password="pass")
        self.user2 = User.objects.create_user(username="m6_u2", email="m6_u2@example.com", password="pass")
        self.user3 = User.objects.create_user(username="m6_u3", email="m6_u3@example.com", password="pass")

        self.player1 = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        self.player2 = Player.objects.create(user=self.user2, game=self.game, color=Player.Color.GREEN)
        self.player3 = Player.objects.create(user=self.user3, game=self.game, color=Player.Color.BLUE)

    # =========================================================================
    # 1. Workflow Tests
    # =========================================================================

    def test_full_workflow_create_start_submit_resolve(self):
        """Standard round lifecycle: pending -> active -> completed with calculated winner and placements."""
        # Create
        round_obj = create_round(self.game, question=self.q1)
        self.assertEqual(round_obj.status, Round.Status.PENDING)
        self.assertEqual(round_obj.number, 1)
        self.assertIsNone(round_obj.winner)
        self.assertIsNone(round_obj.completed_at)

        q = round_obj.get_current_question()
        self.assertIsNotNone(q)
        self.assertEqual(q.sequence, 1)
        self.assertEqual(q.status, RoundQuestion.Status.PENDING)
        self.assertEqual(q.participants.count(), 3)
        self.assertIsNone(q.started_at)
        self.assertIsNone(q.deadline)

        # Start
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        round_obj.refresh_from_db()
        q.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.ACTIVE)
        self.assertEqual(q.status, RoundQuestion.Status.ACTIVE)
        self.assertEqual(q.started_at, t0)
        self.assertEqual(q.deadline, t0 + timedelta(seconds=10))

        # Submit answers (all 3 participants answer before deadline)
        submit_round_answer(round_obj, self.player1, 680, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 685, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 700, current_time=t0 + timedelta(seconds=3))

        # Resolve
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))
        round_obj.refresh_from_db()

        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.player1)
        self.assertIsNotNone(round_obj.completed_at)

        placements = list(round_obj.get_placements())
        self.assertEqual(len(placements), 2)
        self.assertEqual(placements[0].place, 1)
        self.assertEqual(placements[0].player, self.player1)
        self.assertEqual(placements[1].place, 2)
        self.assertEqual(placements[1].player, self.player2)

    def test_round_number_increment_and_gap_preservation(self):
        """Round number is max(existing) + 1; gaps are not filled."""
        r1 = create_round(self.game, question=self.q1)
        self.assertEqual(r1.number, 1)
        t0 = timezone.now()
        start_round(r1, start_time=t0)
        # All 3 answer
        submit_round_answer(r1, self.player1, 681, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(r1, self.player2, 685, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(r1, self.player3, 690, current_time=t0 + timedelta(seconds=3))
        resolve_round(r1, current_time=t0 + timedelta(seconds=4))

        r2 = create_round(self.game, question=self.q2)
        self.assertEqual(r2.number, 2)
        start_round(r2, start_time=t0 + timedelta(seconds=10))
        submit_round_answer(r2, self.player1, 1908, current_time=t0 + timedelta(seconds=11))
        submit_round_answer(r2, self.player2, 1900, current_time=t0 + timedelta(seconds=12))
        submit_round_answer(r2, self.player3, 1950, current_time=t0 + timedelta(seconds=13))
        resolve_round(r2, current_time=t0 + timedelta(seconds=14))

        # Delete round 2 (simulate gap)
        r2.delete()
        r_new = create_round(self.game, question=self.q3)
        self.assertEqual(r_new.number, 2)

    def test_cannot_create_round_if_uncompleted_round_exists(self):
        """In a game, there can be at most one uncompleted round."""
        create_round(self.game, question=self.q1)
        with self.assertRaises(InvalidStateError):
            create_round(self.game, question=self.q2)

    def test_cannot_create_or_mutate_in_non_active_game(self):
        """All round mutating operations require an active game."""
        waiting_game = Game.objects.create(status=Game.Status.WAITING)
        Player.objects.create(user=self.user1, game=waiting_game, color=Player.Color.RED)
        Player.objects.create(user=self.user2, game=waiting_game, color=Player.Color.GREEN)
        Player.objects.create(user=self.user3, game=waiting_game, color=Player.Color.BLUE)

        with self.assertRaises(InvalidStateError):
            create_round(waiting_game, question=self.q1)

    # =========================================================================
    # 2. Answer Ranking & Deterministic Comparison Tests
    # =========================================================================

    def test_proximity_before_speed(self):
        """A closer answer with slower time beats a farther answer with faster time."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # P1: diff 5, submitted at t0 + 0.5s
        submit_round_answer(r, self.player1, 676, current_time=t0 + timedelta(seconds=0.5))
        # P2: diff 1, submitted at t0 + 6.0s
        submit_round_answer(r, self.player2, 680, current_time=t0 + timedelta(seconds=6.0))
        # P3: diff 20, at t0 + 1.0s
        submit_round_answer(r, self.player3, 701, current_time=t0 + timedelta(seconds=1.0))

        resolve_round(r, current_time=t0 + timedelta(seconds=7.0))
        r.refresh_from_db()

        self.assertEqual(r.winner, self.player2)  # Closer answer wins
        placements = list(r.get_placements())
        self.assertEqual(placements[0].player, self.player2)  # 1st: diff 1
        self.assertEqual(placements[1].player, self.player1)  # 2nd: diff 5

    def test_equal_proximity_different_times_speed_wins(self):
        """For equal difference, earlier submitted_at wins, even on opposite sides of correct answer."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # P1 answers 671 (diff 10) at t0 + 1.5s
        submit_round_answer(r, self.player1, 671, current_time=t0 + timedelta(seconds=1.5))
        # P2 answers 691 (diff 10, other side) at t0 + 3.2s
        submit_round_answer(r, self.player2, 691, current_time=t0 + timedelta(seconds=3.2))
        # P3 answers 600 (diff 81) at t0 + 4.0s
        submit_round_answer(r, self.player3, 600, current_time=t0 + timedelta(seconds=4.0))

        resolve_round(r, current_time=t0 + timedelta(seconds=5.0))
        r.refresh_from_db()

        self.assertEqual(r.winner, self.player1)  # Faster time wins
        placements = list(r.get_placements())
        self.assertEqual(placements[0].player, self.player1)
        self.assertEqual(placements[1].player, self.player2)

    def test_single_player_answered(self):
        """If only one player answered within deadline, only 1st place is awarded; no fictional 2nd place."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # Only P1 answers
        submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=2.0))

        # Deadline expires (10 seconds)
        resolve_round(r, current_time=t0 + timedelta(seconds=10.5))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        placements = list(r.get_placements())
        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].place, 1)
        self.assertEqual(placements[0].player, self.player1)
        self.assertIn("only one answer", r.completion_reason)

    # =========================================================================
    # 3. Rejection & Error Handling Tests
    # =========================================================================

    def test_answer_from_foreign_player_rejected(self):
        """Player from another game cannot submit an answer."""
        other_game = Game.objects.create(status=Game.Status.ACTIVE)
        other_user = User.objects.create_user(username="m6_other", email="m6_other@example.com", password="pass")
        other_player = Player.objects.create(user=other_user, game=other_game, color=Player.Color.RED)

        r = create_round(self.game, question=self.q1)
        start_round(r)
        with self.assertRaises(InvalidInputError):
            submit_round_answer(r, other_player, 681)

    def test_duplicate_answer_from_same_player_rejected(self):
        """Player can submit at most one accepted answer per question."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        submit_round_answer(r, self.player1, 680, current_time=t0 + timedelta(seconds=1))
        # Second attempt is rejected
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=2))

    def test_submit_before_start_rejected(self):
        """Cannot submit answer to a pending round."""
        r = create_round(self.game, question=self.q1)
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player1, 681)

    def test_resolve_completed_round_rejected(self):
        """Cannot resolve an already completed round again."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)
        submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=1))
        resolve_round(r, current_time=t0 + timedelta(seconds=11))

        with self.assertRaises(InvalidStateError):
            resolve_round(r, current_time=t0 + timedelta(seconds=12))

    def test_non_integer_input_rejected_without_truncation(self):
        """Non-integer numeric inputs (float, string, boolean) are rejected without quiet truncation."""
        r = create_round(self.game, question=self.q1)
        start_round(r)

        with self.assertRaises(InvalidInputError):
            submit_round_answer(r, self.player1, 681.9)

        with self.assertRaises(InvalidInputError):
            submit_round_answer(r, self.player1, "681")

        with self.assertRaises(InvalidInputError):
            submit_round_answer(r, self.player1, True)

    def test_premature_resolution_rejected(self):
        """Cannot resolve round before all participants have answered and deadline has not expired."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)
        submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=1))

        # Only 1 of 3 answered, and time is at t0 + 5s (deadline is t0 + 10s)
        with self.assertRaises(InvalidStateError):
            resolve_round(r, current_time=t0 + timedelta(seconds=5))

    # =========================================================================
    # 4. Deadline Boundary Tests
    # =========================================================================

    def test_deadline_boundaries(self):
        """Answers before deadline are accepted; exactly on and after deadline are rejected."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)
        deadline = t0 + timedelta(seconds=10)

        # 1. Just before deadline -> Accepted
        ans = submit_round_answer(r, self.player1, 680, current_time=deadline - timedelta(milliseconds=1))
        self.assertIsNotNone(ans)

        # 2. Exactly on deadline -> Rejected
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player2, 680, current_time=deadline)

        # 3. After deadline -> Rejected
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player3, 680, current_time=deadline + timedelta(milliseconds=10))

    # =========================================================================
    # 5. Tie-breaker, Limit, and Bank Exhaustion Tests
    # =========================================================================

    def test_tie_for_first_triggers_new_question_only_for_tied_players(self):
        """Full tie for 1st place triggers a new question only for the tied group."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # P1 and P2 submit exact same answer at exact same time
        submit_time = t0 + timedelta(seconds=2.0)
        submit_round_answer(r, self.player1, 680, current_time=submit_time)
        submit_round_answer(r, self.player2, 680, current_time=submit_time)
        submit_round_answer(r, self.player3, 700, current_time=submit_time)

        # Resolve Q1 (all 3 answered)
        resolve_round(r, current_time=t0 + timedelta(seconds=3.0))
        r.refresh_from_db()

        # Round is still ACTIVE with a second question
        self.assertEqual(r.status, Round.Status.ACTIVE)
        self.assertEqual(r.questions.count(), 2)

        q2 = r.get_current_question()
        self.assertEqual(q2.sequence, 2)
        self.assertEqual(q2.status, RoundQuestion.Status.ACTIVE)
        self.assertEqual(set(q2.participants.all()), {self.player1, self.player2})

        # P3 cannot answer Q2
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player3, q2.correct_answer, current_time=t0 + timedelta(seconds=4.0))

        # P1 gives the exact correct answer to Q2, P2 gives correct + 10
        submit_round_answer(r, self.player1, q2.correct_answer, current_time=t0 + timedelta(seconds=4.0))
        submit_round_answer(r, self.player2, q2.correct_answer + 10, current_time=t0 + timedelta(seconds=5.0))

        resolve_round(r, current_time=t0 + timedelta(seconds=6.0))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        self.assertEqual(r.placements.get(place=1).player, self.player1)
        self.assertEqual(r.placements.get(place=2).player, self.player2)

    def test_tie_for_second_preserves_first_place(self):
        """A tie for 2nd place preserves the undisputed 1st place and asks new question only for 2nd."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # P1 is clear 1st
        submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=1.0))
        # P2 and P3 tie for 2nd place
        tie_time = t0 + timedelta(seconds=2.0)
        submit_round_answer(r, self.player2, 690, current_time=tie_time)
        submit_round_answer(r, self.player3, 690, current_time=tie_time)

        resolve_round(r, current_time=t0 + timedelta(seconds=3.0))
        r.refresh_from_db()

        # 1st place is already recorded for P1!
        self.assertTrue(r.placements.filter(place=1, player=self.player1).exists())

        # Q2 is created for P2 and P3 only
        q2 = r.get_current_question()
        self.assertEqual(q2.sequence, 2)
        self.assertEqual(set(q2.participants.all()), {self.player2, self.player3})

        # P1 cannot answer Q2
        with self.assertRaises(InvalidStateError):
            submit_round_answer(r, self.player1, q2.correct_answer, current_time=t0 + timedelta(seconds=4.0))

        # P3 answers exactly correct, P2 answers + 50
        submit_round_answer(r, self.player3, q2.correct_answer, current_time=t0 + timedelta(seconds=4.0))
        submit_round_answer(r, self.player2, q2.correct_answer + 50, current_time=t0 + timedelta(seconds=5.0))

        resolve_round(r, current_time=t0 + timedelta(seconds=6.0))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        self.assertEqual(r.placements.get(place=1).player, self.player1)
        self.assertEqual(r.placements.get(place=2).player, self.player3)

    def test_no_answers_triggers_new_question_for_same_group(self):
        """When no answers are received, a new question is activated for the same group."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # Deadline expires with 0 answers
        resolve_round(r, current_time=t0 + timedelta(seconds=11))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.ACTIVE)
        self.assertEqual(r.questions.count(), 2)
        q2 = r.get_current_question()
        self.assertEqual(q2.sequence, 2)
        self.assertEqual(set(q2.participants.all()), {self.player1, self.player2, self.player3})

    def test_max_limit_of_three_questions_ends_round(self):
        """After 3 questions, if places remain unresolved, round completes with 'limit_reached'."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # Q1 expires with 0 answers -> triggers Q2
        resolve_round(r, current_time=t0 + timedelta(seconds=11))
        # Q2 expires with 0 answers -> triggers Q3
        resolve_round(r, current_time=t0 + timedelta(seconds=22))
        # Q3 expires with 0 answers -> limit reached!
        resolve_round(r, current_time=t0 + timedelta(seconds=33))

        r.refresh_from_db()
        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertIsNone(r.winner)
        self.assertEqual(r.completion_reason, "limit_reached")
        self.assertIsNotNone(r.completed_at)

    def test_bank_exhausted_ends_round(self):
        """When tie occurs and bank has no more questions, round completes with 'question_bank_exhausted'."""
        # Delete questions q2, q3, q4 so only q1 exists in database
        NumericQuestion.objects.filter(id__in=[self.q2.id, self.q3.id, self.q4.id]).delete()

        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # 0 answers -> no questions left in bank for Q2
        resolve_round(r, current_time=t0 + timedelta(seconds=11))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertIsNone(r.winner)
        self.assertEqual(r.completion_reason, "question_bank_exhausted")
        self.assertIsNotNone(r.completed_at)

    def test_victory_on_third_question_is_valid(self):
        """A determined outcome on the 3rd question is valid; the limit does not negate victory."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)

        # Q1: 0 answers -> Q2
        resolve_round(r, current_time=t0 + timedelta(seconds=11))
        # Q2: 0 answers -> Q3
        resolve_round(r, current_time=t0 + timedelta(seconds=22))

        # Q3: P1, P2, P3 answer
        q3 = r.get_current_question()
        q3_time = t0 + timedelta(seconds=23)
        submit_round_answer(r, self.player1, q3.correct_answer, current_time=q3_time)
        submit_round_answer(r, self.player2, q3.correct_answer + 10, current_time=q3_time + timedelta(seconds=1))
        submit_round_answer(r, self.player3, q3.correct_answer + 50, current_time=q3_time + timedelta(seconds=2))

        # All 3 answered Q3 -> can resolve immediately
        resolve_round(r, current_time=t0 + timedelta(seconds=26))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.Status.COMPLETED)
        self.assertEqual(r.winner, self.player1)
        self.assertEqual(r.placements.get(place=1).player, self.player1)
        self.assertEqual(r.placements.get(place=2).player, self.player2)

    # =========================================================================
    # 6. Data Immutability & Persistence Tests
    # =========================================================================

    def test_reloading_restores_current_question_deadline_and_rankings(self):
        """Reloading models from the DB accurately restores question, remaining time, and placements."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)
        # All 3 answer
        submit_round_answer(r, self.player1, 681, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(r, self.player2, 685, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(r, self.player3, 690, current_time=t0 + timedelta(seconds=3))

        # Check remaining seconds calculation
        q = r.get_current_question()
        remaining = q.get_remaining_seconds(current_time=t0 + timedelta(seconds=3))
        self.assertAlmostEqual(remaining, 7.0, places=1)

        resolve_round(r, current_time=t0 + timedelta(seconds=4))

        # Reload clean from DB
        fresh_round = Round.objects.get(pk=r.pk)
        self.assertEqual(fresh_round.status, Round.Status.COMPLETED)
        self.assertEqual(fresh_round.winner, self.player1)
        self.assertEqual(fresh_round.get_placements().count(), 2)

    def test_bank_question_modification_does_not_affect_round_history(self):
        """Modifying the bank question after round creation does not affect snapshot history."""
        r = create_round(self.game, question=self.q1)
        q_snapshot = r.get_current_question()

        # Modify bank question
        self.q1.text = "Модифициран текст!"
        self.q1.correct_answer = 9999
        self.q1.save()

        # Snapshot in round remains unchanged
        q_snapshot.refresh_from_db()
        self.assertEqual(q_snapshot.question_text, "През коя година е основана българската държава?")
        self.assertEqual(q_snapshot.correct_answer, 681)

    # =========================================================================
    # 7. Model Validation Tests
    # =========================================================================

    def test_completed_round_without_winner_requires_completion_reason(self):
        """A completed round without winner is valid only with a specified completion_reason."""
        r = Round(game=self.game, number=1, type=Round.Type.CITY_CAPTURE, status=Round.Status.COMPLETED, completed_at=timezone.now(), winner=None)
        # Without reason -> fails validation
        with self.assertRaises(ValidationError):
            r.full_clean()

        # With reason -> passes validation
        r.completion_reason = "limit_reached"
        r.full_clean()

    # =========================================================================
    # 8. Advanced Concurrency Constraint Test
    # =========================================================================

    def test_database_constraint_prevents_simultaneous_duplicate_answers(self):
        """Database unique constraint guarantees only one answer per player per question."""
        r = create_round(self.game, question=self.q1)
        t0 = timezone.now()
        start_round(r, start_time=t0)
        q = r.get_current_question()

        RoundAnswer.objects.create(
            round_question=q,
            player=self.player1,
            answer=681,
            difference=0,
            submitted_at=t0 + timedelta(seconds=1),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoundAnswer.objects.create(
                    round_question=q,
                    player=self.player1,
                    answer=685,
                    difference=4,
                    submitted_at=t0 + timedelta(seconds=1),
                )
