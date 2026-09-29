from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.test import TestCase
from questions.models import Category, ChoiceQuestion, NumericQuestion, AnswerOption


class ModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="История")

    def test_category_creation_and_unique_name(self):
        """Създаване на категория: валидно име и уникално име."""
        self.assertEqual(self.category.name, "История")
        self.assertEqual(str(self.category), "История")

        with self.assertRaises(IntegrityError):
            Category.objects.create(name="История")

    def test_choice_question_creation_valid(self):
        """Създаване на валиден choice въпрос: 4 отговора, точно 1 правилен."""
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Коя година е основана България?"
        )
        AnswerOption.objects.create(question=question, text="681", is_correct=True)
        AnswerOption.objects.create(question=question, text="865", is_correct=False)
        AnswerOption.objects.create(question=question, text="1018", is_correct=False)
        AnswerOption.objects.create(question=question, text="1185", is_correct=False)

        # Validation should succeed
        try:
            question.clean()
        except ValidationError:
            self.fail("Valid choice question raised ValidationError unexpectedly!")

        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)
        self.assertEqual(str(question), "Коя година е основана България?")

    def test_choice_question_invalid_options_count(self):
        """Невалиден choice въпрос: по-малко или повече от четири отговора."""
        # 3 options (fewer than 4)
        question1 = ChoiceQuestion.objects.create(
            category=self.category,
            text="Тестов въпрос с 3 отговора"
        )
        AnswerOption.objects.create(question=question1, text="A", is_correct=True)
        AnswerOption.objects.create(question=question1, text="B", is_correct=False)
        AnswerOption.objects.create(question=question1, text="C", is_correct=False)

        with self.assertRaises(ValidationError):
            question1.clean()

        # 5 options (more than 4)
        AnswerOption.objects.create(question=question1, text="D", is_correct=False)
        AnswerOption.objects.create(question=question1, text="E", is_correct=False)
        with self.assertRaises(ValidationError):
            question1.clean()

    def test_choice_question_invalid_correct_count(self):
        """Невалиден choice въпрос: няма правилен отговор или повече от един правилен."""
        # 0 correct
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос без верен отговор"
        )
        for i in range(4):
            AnswerOption.objects.create(question=question, text=f"Опция {i}", is_correct=False)

        with self.assertRaises(ValidationError):
            question.clean()

        # 2 correct
        options = list(question.options.all())
        options[0].is_correct = True
        options[0].save()
        options[1].is_correct = True
        options[1].save()

        with self.assertRaises(ValidationError):
            question.clean()

    def test_numeric_question_creation(self):
        """Създаване на numeric въпрос: категория, текст, правилен числов отговор."""
        num_q = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е освободена България?",
            correct_answer=1878
        )
        self.assertEqual(num_q.correct_answer, 1878)
        self.assertEqual(num_q.category, self.category)
        self.assertEqual(str(num_q), "През коя година е освободена България?")

        # clean() passes
        try:
            num_q.clean()
        except ValidationError:
            self.fail("Valid numeric question raised ValidationError unexpectedly!")

    def test_delete_choice_question_cascades_options(self):
        """Изтриване на choice въпрос: изтриване на свързаните answer options."""
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос за триене"
        )
        for i in range(4):
            AnswerOption.objects.create(question=question, text=f"Отговор {i}", is_correct=(i == 0))

        option_ids = list(question.options.values_list('id', flat=True))
        self.assertEqual(len(option_ids), 4)

        question.delete()

        # Options must be deleted
        remaining_options = AnswerOption.objects.filter(id__in=option_ids).count()
        self.assertEqual(remaining_options, 0)

    def test_protected_category(self):
        """Защитена категория: категория с въпроси не може да бъде изтрита."""
        ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос свързан с категорията"
        )

        with self.assertRaises(models.ProtectedError):
            self.category.delete()
