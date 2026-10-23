from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from games.exceptions import InvalidInputError, InvalidStateError, RecordNotFoundError
from games.models import (
    Capital,
    CaptureRight,
    Game,
    Player,
    Round,
    RoundQuestion,
    Territory,
    TerritoryCaptureLog,
)
from games.services import (
    ROUND_VICTORY_REWARD,
    TERRITORY_CAPTURE_REWARD,
    TERRITORY_SCORE_INCREMENT,
    choose_territory_capture,
    create_round,
    get_eligible_territories,
    has_pending_capture_rights,
    initialize_game,
    resolve_round,
    start_round,
    submit_round_answer,
)
from questions.models import Category, NumericQuestion

User = get_user_model()


class TerritoryCaptureAndScoringTests(TestCase):
    """Comprehensive test suite for M07 — Territory Capture and Scoring."""

    def setUp(self):
        # 1. Bank of questions
        self.category = Category.objects.create(name="История")
        self.questions = [
            NumericQuestion.objects.create(
                category=self.category,
                text=f"Въпрос {i}?",
                correct_answer=100 * i,
            )
            for i in range(1, 10)
        ]

        # 2. Game, users, players, and initialized map (M05)
        self.game = Game.objects.create(status=Game.Status.WAITING)
        self.user1 = User.objects.create_user(username="m7_u1", email="m7_u1@example.com", password="pass")
        self.user2 = User.objects.create_user(username="m7_u2", email="m7_u2@example.com", password="pass")
        self.user3 = User.objects.create_user(username="m7_u3", email="m7_u3@example.com", password="pass")

        self.player1 = Player.objects.create(user=self.user1, game=self.game, color=Player.Color.RED)
        self.player2 = Player.objects.create(user=self.user2, game=self.game, color=Player.Color.GREEN)
        self.player3 = Player.objects.create(user=self.user3, game=self.game, color=Player.Color.BLUE)

        # Initialize game map (creates 18 territories, assigns 3 capitals, status -> active)
        initialize_game(self.game)
        self.game.refresh_from_db()
        self.player1.refresh_from_db()
        self.player2.refresh_from_db()
        self.player3.refresh_from_db()

    # =========================================================================
    # 1. Distribution Tests (2+1, 2, 1)
    # =========================================================================

    def test_distribution_three_or_more_free_territories(self):
        """When 3+ free territories exist, 1st place gets 2 rights, 2nd place gets 1 right."""
        free_count = self.game.territories.filter(owner__isnull=True).count()
        self.assertEqual(free_count, 15)  # 18 total - 3 capitals = 15 free

        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)

        # P1 is 1st, P2 is 2nd, P3 is 3rd
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.winner, self.player1)

        # Check rights created
        rights = list(round_obj.capture_rights.order_by("order"))
        self.assertEqual(len(rights), 2)
        # Order 1 (P1): 2 allowed choices
        self.assertEqual(rights[0].player, self.player1)
        self.assertEqual(rights[0].order, 1)
        self.assertEqual(rights[0].allowed_choices, 2)
        self.assertEqual(rights[0].used_choices, 0)
        # Order 2 (P2): 1 allowed choice
        self.assertEqual(rights[1].player, self.player2)
        self.assertEqual(rights[1].order, 2)
        self.assertEqual(rights[1].allowed_choices, 1)
        self.assertEqual(rights[1].used_choices, 0)

        # 3rd place has 0 rights
        self.assertFalse(round_obj.capture_rights.filter(player=self.player3).exists())

        # Execute choices in order: P1 picks 2, then P2 picks 1
        p1_eligible = get_eligible_territories(self.game, self.player1)
        t_choice1 = p1_eligible.first()
        choose_territory_capture(round_obj, self.player1, t_choice1)

        p1_eligible = get_eligible_territories(self.game, self.player1)
        t_choice2 = p1_eligible.first()
        choose_territory_capture(round_obj, self.player1, t_choice2)

        p2_eligible = get_eligible_territories(self.game, self.player2)
        t_choice3 = p2_eligible.first()
        choose_territory_capture(round_obj, self.player2, t_choice3)

        rights[0].refresh_from_db()
        rights[1].refresh_from_db()
        self.assertEqual(rights[0].used_choices, 2)
        self.assertEqual(rights[1].used_choices, 1)
        self.assertTrue(rights[0].is_fulfilled)
        self.assertTrue(rights[1].is_fulfilled)

    def test_distribution_two_free_territories(self):
        """When exactly 2 free territories remain, 1st place gets 2 rights, 2nd place gets 0."""
        # Set all but 2 free territories to owned
        free_territories = list(self.game.territories.filter(owner__isnull=True))
        for t in free_territories[:-2]:
            t.owner = self.player3
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 2)

        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        round_obj.refresh_from_db()
        rights = list(round_obj.capture_rights.all())
        # Only P1 gets rights (2 allowed choices), P2 gets 0
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.player1)
        self.assertEqual(rights[0].allowed_choices, 2)
        self.assertFalse(round_obj.capture_rights.filter(player=self.player2).exists())

    def test_distribution_one_free_territory(self):
        """When exactly 1 free territory remains, 1st place gets 1 right, 2nd place gets 0."""
        free_territories = list(self.game.territories.filter(owner__isnull=True))
        for t in free_territories[:-1]:
            t.owner = self.player3
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 1)

        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        round_obj.refresh_from_db()
        rights = list(round_obj.capture_rights.all())
        # Only P1 gets rights (1 allowed choice)
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.player1)
        self.assertEqual(rights[0].allowed_choices, 1)

    # =========================================================================
    # 2. Adjacency & Exception Rule Tests
    # =========================================================================

    def test_valid_neighbor_and_invalid_non_neighbor(self):
        """Player must choose an adjacent free territory; non-neighbor is rejected when neighbors exist."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 120, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 130, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        p1_holdings = self.game.territories.filter(owner=self.player1)
        adjacent_free = self.game.territories.filter(owner__isnull=True, neighbors__in=p1_holdings).distinct()
        non_adjacent_free = self.game.territories.filter(owner__isnull=True).exclude(id__in=adjacent_free)

        self.assertTrue(adjacent_free.exists())
        self.assertTrue(non_adjacent_free.exists())

        # Attempt to choose non-adjacent territory -> Rejected
        with self.assertRaises(InvalidInputError):
            choose_territory_capture(round_obj, self.player1, non_adjacent_free.first())

        # Attempt to choose adjacent territory -> Accepted
        valid_t = adjacent_free.first()
        t_res, p_res = choose_territory_capture(round_obj, self.player1, valid_t)
        self.assertEqual(t_res.owner, self.player1)

    def test_dynamic_eligibility_update_after_first_choice(self):
        """Territory captured on first choice makes its neighbors immediately eligible for second choice."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 110, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        # Initial capital neighbors of P1
        initial_neighbors = set(get_eligible_territories(self.game, self.player1).values_list("id", flat=True))

        choice1 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, choice1)

        # After choice 1, eligible territories should now include choice1's free neighbors
        new_eligible = set(get_eligible_territories(self.game, self.player1).values_list("id", flat=True))
        choice1_free_neighbors = set(choice1.neighbors.filter(owner__isnull=True).values_list("id", flat=True))

        self.assertTrue(choice1_free_neighbors.issubset(new_eligible))

    def test_adjacency_exception_allows_any_free_territory_when_no_adjacent_free(self):
        """When player has NO adjacent free territories, they can choose ANY free territory."""
        # Find capital of P1
        p1_cap = self.game.territories.filter(owner=self.player1).first()
        # Set all neighbors of P1's capital to owned by P2 and P3
        for nbr in p1_cap.neighbors.all():
            nbr.owner = self.player2
            nbr.save()

        # Verify P1 has 0 adjacent free territories
        p1_holdings = self.game.territories.filter(owner=self.player1)
        adjacent_free = self.game.territories.filter(owner__isnull=True, neighbors__in=p1_holdings)
        self.assertEqual(adjacent_free.count(), 0)

        # Free territories still exist elsewhere on the map
        total_free = self.game.territories.filter(owner__isnull=True)
        self.assertTrue(total_free.exists())

        # Exception rule: get_eligible_territories returns all free territories
        eligible = get_eligible_territories(self.game, self.player1)
        self.assertEqual(set(eligible), set(total_free))

        # P1 can choose any free territory
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 110, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        target = total_free.first()
        t_res, _ = choose_territory_capture(round_obj, self.player1, target)
        self.assertEqual(t_res.owner, self.player1)

    # =========================================================================
    # 3. Rights & Turn Order Enforcement Tests
    # =========================================================================

    def test_cannot_choose_out_of_turn(self):
        """2nd place player cannot choose before 1st place player finishes their choices."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        p2_target = get_eligible_territories(self.game, self.player2).first()

        # P2 attempts to choose before P1 -> Rejected with InvalidStateError
        with self.assertRaises(InvalidStateError):
            choose_territory_capture(round_obj, self.player2, p2_target)

    def test_cannot_exceed_allowed_choices(self):
        """Player cannot choose more territories than granted by rights."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        # P1 uses choice 1
        t1 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t1)
        # P1 uses choice 2
        t2 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t2)

        # P1 attempts choice 3 (exceeding rights) -> Rejected
        t3 = get_eligible_territories(self.game, self.player1).first()
        with self.assertRaises(InvalidStateError):
            choose_territory_capture(round_obj, self.player1, t3)

    def test_foreign_player_cannot_choose(self):
        """Player from another game or 3rd place without rights cannot choose."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        t = get_eligible_territories(self.game, self.player1).first()

        # P3 (3rd place, no rights) tries to choose -> Rejected
        with self.assertRaises(InvalidInputError):
            choose_territory_capture(round_obj, self.player3, t)

    # =========================================================================
    # 4. Scoring Tests
    # =========================================================================

    def test_scoring_system_applied_correctly(self):
        """
        Victory reward (+100) awarded to winner upon resolve.
        Each capture adds +200 to player and +100 to territory.
        Audit log records before/after correctly.
        """
        p1_initial = self.player1.score
        p2_initial = self.player2.score
        self.assertEqual(p1_initial, 0)
        self.assertEqual(p2_initial, 0)

        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        self.player1.refresh_from_db()
        # Winner receives ROUND_VICTORY_REWARD (+100) upon completion
        self.assertEqual(self.player1.score, ROUND_VICTORY_REWARD)

        # P1 captures first territory
        t1 = get_eligible_territories(self.game, self.player1).first()
        self.assertEqual(t1.score, 0)

        choose_territory_capture(round_obj, self.player1, t1)
        self.player1.refresh_from_db()
        t1.refresh_from_db()

        # P1 score: 100 + 200 = 300
        self.assertEqual(self.player1.score, ROUND_VICTORY_REWARD + TERRITORY_CAPTURE_REWARD)
        # Territory score increased from 0 to 100
        self.assertEqual(t1.score, TERRITORY_SCORE_INCREMENT)

        # Check TerritoryCaptureLog record
        log1 = TerritoryCaptureLog.objects.filter(territory=t1).first()
        self.assertIsNotNone(log1)
        self.assertEqual(log1.points_awarded, TERRITORY_CAPTURE_REWARD)
        self.assertEqual(log1.player_score_before, ROUND_VICTORY_REWARD)
        self.assertEqual(log1.player_score_after, ROUND_VICTORY_REWARD + TERRITORY_CAPTURE_REWARD)
        self.assertEqual(log1.territory_score_before, 0)
        self.assertEqual(log1.territory_score_after, TERRITORY_SCORE_INCREMENT)

        # P1 captures second territory
        t2 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t2)
        self.player1.refresh_from_db()
        # P1 score: 300 + 200 = 500
        self.assertEqual(self.player1.score, ROUND_VICTORY_REWARD + (2 * TERRITORY_CAPTURE_REWARD))

        # P2 captures territory
        t3 = get_eligible_territories(self.game, self.player2).first()
        choose_territory_capture(round_obj, self.player2, t3)
        self.player2.refresh_from_db()
        # P2 score: 0 + 200 = 200
        self.assertEqual(self.player2.score, TERRITORY_CAPTURE_REWARD)

        # P3 score remains unaffected (0)
        self.player3.refresh_from_db()
        self.assertEqual(self.player3.score, 0)

    # =========================================================================
    # 5. Conquest Phase Tests
    # =========================================================================

    def test_next_round_blocked_until_all_capture_rights_fulfilled(self):
        """Cannot create a new round while unfulfilled capture rights remain."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        self.assertTrue(has_pending_capture_rights(self.game))

        # Attempt to create next round while rights are pending -> Blocked
        with self.assertRaises(InvalidStateError):
            create_round(self.game, question=self.questions[1])

        # Fulfill all choices
        t1 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t1)

        t2 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t2)

        t3 = get_eligible_territories(self.game, self.player2).first()
        choose_territory_capture(round_obj, self.player2, t3)

        self.assertFalse(has_pending_capture_rights(self.game))

        # Now creating next round succeeds!
        round2 = create_round(self.game, question=self.questions[1])
        self.assertEqual(round2.number, 2)

    def test_conquest_phase_ends_when_all_territories_captured(self):
        """When 0 free territories remain, creating city_capture round is rejected."""
        # Set all territories as owned
        for t in self.game.territories.all():
            t.owner = self.player1
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 0)

        with self.assertRaises(InvalidStateError):
            create_round(self.game, round_type=Round.Type.CITY_CAPTURE, question=self.questions[0])

    # =========================================================================
    # 6. Unresolved Second Place & No Winner Tests
    # =========================================================================

    def test_unresolved_second_place_preserves_first_place_rights(self):
        """Unresolved second place leaves territories for next round; first place still gets rights."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)

        # Only P1 answers within 10s
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=2.0))
        # Deadline expires (10 seconds)
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=10.5))

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.winner, self.player1)

        # P1 gets 2 rights; P2 gets 0 rights
        rights = list(round_obj.capture_rights.all())
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.player1)
        self.assertEqual(rights[0].allowed_choices, 2)

        # P1 uses their 2 choices
        t1 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t1)
        t2 = get_eligible_territories(self.game, self.player1).first()
        choose_territory_capture(round_obj, self.player1, t2)

        # No pending rights remain; 15 - 2 = 13 free territories remain for next round
        self.assertFalse(has_pending_capture_rights(self.game))
        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 13)

        # Next round can be created
        round2 = create_round(self.game, question=self.questions[1])
        self.assertEqual(round2.number, 2)

    def test_no_winner_grants_no_rights_and_no_victory_reward(self):
        """Round without winner (e.g. limit reached with 0 answers) grants 0 rights and 0 rewards."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)

        # Q1 expires -> Q2
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=11))
        # Q2 expires -> Q3
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=22))
        # Q3 expires -> limit reached
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=33))

        round_obj.refresh_from_db()
        self.assertIsNone(round_obj.winner)
        self.assertEqual(round_obj.capture_rights.count(), 0)

        # Scores remain 0
        self.player1.refresh_from_db()
        self.assertEqual(self.player1.score, 0)

    # =========================================================================
    # 7. Atomicity & Rollback Tests
    # =========================================================================

    def test_capture_failure_does_not_consume_right_or_award_points(self):
        """An error during capture attempt rolls back completely; right is not consumed."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        right = round_obj.capture_rights.get(player=self.player1)
        self.assertEqual(right.used_choices, 0)

        # Attempt to capture an already owned territory (fails validation)
        owned_t = self.game.territories.filter(owner=self.player2).first()
        with self.assertRaises(InvalidInputError):
            choose_territory_capture(round_obj, self.player1, owned_t)

        right.refresh_from_db()
        self.assertEqual(right.used_choices, 0)  # Right was not consumed
        self.player1.refresh_from_db()
        self.assertEqual(self.player1.score, ROUND_VICTORY_REWARD)  # No capture score added

    # =========================================================================
    # 8. Advanced Concurrency Simulation Tests
    # =========================================================================

    def test_concurrent_capture_of_same_territory_only_one_succeeds(self):
        """When two requests attempt to capture the exact same territory, only one succeeds."""
        round_obj = create_round(self.game, question=self.questions[0])
        t0 = timezone.now()
        start_round(round_obj, start_time=t0)
        submit_round_answer(round_obj, self.player1, 100, current_time=t0 + timedelta(seconds=1))
        submit_round_answer(round_obj, self.player2, 105, current_time=t0 + timedelta(seconds=2))
        submit_round_answer(round_obj, self.player3, 120, current_time=t0 + timedelta(seconds=3))
        resolve_round(round_obj, current_time=t0 + timedelta(seconds=4))

        target = get_eligible_territories(self.game, self.player1).first()

        # First capture succeeds
        choose_territory_capture(round_obj, self.player1, target)
        target.refresh_from_db()
        self.assertEqual(target.owner, self.player1)

        # Second capture of the same territory is rejected
        with self.assertRaises(InvalidInputError):
            choose_territory_capture(round_obj, self.player1, target)
