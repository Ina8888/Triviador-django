from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile

User = get_user_model()


class ModelTests(TestCase):
    def test_user_creation_and_email(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="securepassword123"
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("securepassword123"))
        self.assertFalse(user.check_password("wrongpassword"))

    def test_profile_creation_and_defaults(self):
        user = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="securepassword123"
        )
        profile = Profile.objects.create(
            user=user,
            nickname="TestKnight"
        )
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.nickname, "TestKnight")
        self.assertEqual(profile.avatar_key, "knight-1")
        self.assertEqual(user.profile, profile)
