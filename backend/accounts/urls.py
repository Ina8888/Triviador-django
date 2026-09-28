from django.urls import path
from .views import CSRFView, RegisterView, LoginView, LogoutView, MeView

app_name = 'accounts'

urlpatterns = [
    path('csrf/', CSRFView.as_view(), name='csrf'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
]
