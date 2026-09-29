import random
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ChoiceQuestion
from .serializers import ChoiceQuestionSerializer


class RandomChoiceQuestionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        count = ChoiceQuestion.objects.count()
        if count == 0:
            return Response(
                {"errors": {"detail": "No questions available in the question bank."}},
                status=status.HTTP_404_NOT_FOUND
            )
        random_index = random.randint(0, count - 1)
        question = ChoiceQuestion.objects.all()[random_index]
        serializer = ChoiceQuestionSerializer(question)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChoiceQuestionListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        questions = ChoiceQuestion.objects.all().prefetch_related('options', 'category')
        serializer = ChoiceQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
