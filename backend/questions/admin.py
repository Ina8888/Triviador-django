from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Category, ChoiceQuestion, NumericQuestion, AnswerOption


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class AnswerOptionInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        valid_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        if len(valid_forms) != 4:
            raise ValidationError("ChoiceQuestion must have exactly 4 answer options.")

        correct_count = sum(
            1 for form in valid_forms
            if form.cleaned_data.get('is_correct', False)
        )
        if correct_count != 1:
            raise ValidationError("ChoiceQuestion must have exactly one correct answer.")


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    formset = AnswerOptionInlineFormSet
    extra = 4
    min_num = 4
    max_num = 4


@admin.register(ChoiceQuestion)
class ChoiceQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'category')
    list_filter = ('category',)
    search_fields = ('text',)
    inlines = [AnswerOptionInline]


@admin.register(NumericQuestion)
class NumericQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'category', 'correct_answer')
    list_filter = ('category',)
    search_fields = ('text',)
