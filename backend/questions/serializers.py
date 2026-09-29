from rest_framework import serializers
from .models import Category, ChoiceQuestion, AnswerOption, NumericQuestion


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ['id', 'text', 'is_correct']


class ChoiceQuestionSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)
    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ChoiceQuestion
        fields = ['id', 'category', 'text', 'options']


class NumericQuestionSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = NumericQuestion
        fields = ['id', 'category', 'text', 'correct_answer']
