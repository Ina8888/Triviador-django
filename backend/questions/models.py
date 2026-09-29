from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class BaseQuestion(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
    )
    text = models.TextField()

    class Meta:
        abstract = True

    def __str__(self):
        return self.text


class ChoiceQuestion(BaseQuestion):
    class Meta:
        verbose_name = "Choice Question"
        verbose_name_plural = "Choice Questions"

    def clean(self):
        super().clean()
        if self.pk:
            options = self.options.all()
            count = options.count()
            if count != 4:
                raise ValidationError("ChoiceQuestion must have exactly 4 answer options.")
            correct_count = options.filter(is_correct=True).count()
            if correct_count != 1:
                raise ValidationError("ChoiceQuestion must have exactly one correct answer.")


class NumericQuestion(BaseQuestion):
    correct_answer = models.IntegerField()

    class Meta:
        verbose_name = "Numeric Question"
        verbose_name_plural = "Numeric Questions"

    def clean(self):
        super().clean()
        if self.correct_answer is None:
            raise ValidationError("NumericQuestion must have a correct integer answer.")


class AnswerOption(models.Model):
    question = models.ForeignKey(
        ChoiceQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Answer Option"
        verbose_name_plural = "Answer Options"

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"
