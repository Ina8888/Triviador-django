from django.core.management import call_command
from django.test import TestCase
from questions.models import Category, ChoiceQuestion, NumericQuestion, AnswerOption


class FixtureTests(TestCase):
    def setUp(self):
        call_command('loaddata', 'questions/question_bank.json', verbosity=0)

    def test_fixture_loading_counts(self):
        """Зареждане на fixture: проверка на точния брой записи."""
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(ChoiceQuestion.objects.count(), 12)
        self.assertEqual(AnswerOption.objects.count(), 48)
        self.assertEqual(NumericQuestion.objects.count(), 12)

    def test_fixture_choice_questions_validity(self):
        """Валидност на fixture данните: всеки choice въпрос има 4 отговора и точно 1 правилен."""
        for question in ChoiceQuestion.objects.all():
            options = question.options.all()
            self.assertEqual(
                options.count(),
                4,
                f"Въпрос '{question.text}' няма точно 4 опции!"
            )
            correct_count = options.filter(is_correct=True).count()
            self.assertEqual(
                correct_count,
                1,
                f"Въпрос '{question.text}' няма точно 1 правилен отговор!"
            )
            # clean() validation passes
            question.clean()

    def test_fixture_numeric_questions_validity(self):
        """Валидност на fixture данните: всеки numeric въпрос има валиден числов отговор."""
        for question in NumericQuestion.objects.all():
            self.assertIsNotNone(question.correct_answer)
            self.assertIsInstance(question.correct_answer, int)
            question.clean()
