from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile
from accounts.serializers import RegisterSerializer, ProfileUpdateSerializer

User = get_user_model()


class SerializerTests(TestCase):
    def test_register_serializer_password_mismatch(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "nickname": "NewKnight",
            "password": "pass1",
            "password_confirm": "pass2",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password_confirm", serializer.errors)

    def test_profile_update_serializer_unique_nickname(self):
        user1 = User.objects.create_user(username="u1", email="u1@example.com", password="pwd")
        Profile.objects.create(user=user1, nickname="KnightOne")

        user2 = User.objects.create_user(username="u2", email="u2@example.com", password="pwd")
        p2 = Profile.objects.create(user=user2, nickname="KnightTwo")

        serializer = ProfileUpdateSerializer(instance=p2, data={"nickname": "KnightOne"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("nickname", serializer.errors)
