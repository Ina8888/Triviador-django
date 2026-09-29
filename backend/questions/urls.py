from django.urls import path
from .views import RandomChoiceQuestionView, ChoiceQuestionListView

app_name = 'questions'

urlpatterns = [
    path('random/', RandomChoiceQuestionView.as_view(), name='random'),
    path('', ChoiceQuestionListView.as_view(), name='list'),
]
