from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from accounts.models import Profile

User = get_user_model()


class AuthAPITests(APITestCase):
    def setUp(self):
        self.register_url = reverse('accounts:register')
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')
        self.me_url = reverse('accounts:me')
        self.csrf_url = reverse('accounts:csrf')

    def test_01_successful_registration(self):
        """1. Успешна регистрация (201 Created, създаден User и Profile, hash-ната парола, без парола в response)."""
        data = {
            "username": "player_one",
            "email": "player@example.com",
            "nickname": "MountainKnight",
            "password": "example-password",
            "password_confirm": "example-password"
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["username"], "player_one")
        self.assertEqual(response.data["email"], "player@example.com")
        self.assertEqual(response.data["profile"]["nickname"], "MountainKnight")
        self.assertEqual(response.data["profile"]["avatar_key"], "knight-1")

        # Database checks
        user = User.objects.get(username="player_one")
        self.assertEqual(user.email, "player@example.com")
        self.assertTrue(user.check_password("example-password"))
        self.assertEqual(user.profile.nickname, "MountainKnight")

    def test_02_invalid_registration(self):
        """2. Невалидна регистрация (зает username/email/nickname, пароли не съвпадат -> 400)."""
        # Create an existing user
        user = User.objects.create_user(username="existing", email="existing@example.com", password="pwd")
        Profile.objects.create(user=user, nickname="ExistingKnight")
        initial_user_count = User.objects.count()

        cases = [
            # Taken username
            {
                "data": {"username": "existing", "email": "new@example.com", "nickname": "NewNick1", "password": "pwd", "password_confirm": "pwd"},
                "expected_field": "username"
            },
            # Taken email
            {
                "data": {"username": "newuser2", "email": "existing@example.com", "nickname": "NewNick2", "password": "pwd", "password_confirm": "pwd"},
                "expected_field": "email"
            },
            # Taken nickname
            {
                "data": {"username": "newuser3", "email": "new3@example.com", "nickname": "ExistingKnight", "password": "pwd", "password_confirm": "pwd"},
                "expected_field": "nickname"
            },
            # Password mismatch
            {
                "data": {"username": "newuser4", "email": "new4@example.com", "nickname": "NewNick4", "password": "pwd1", "password_confirm": "pwd2"},
                "expected_field": "password_confirm"
            },
        ]

        for case in cases:
            with self.subTest(case=case["expected_field"]):
                response = self.client.post(self.register_url, case["data"], format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("errors", response.data)
                self.assertIn(case["expected_field"], response.data["errors"])

        # No additional users created
        self.assertEqual(User.objects.count(), initial_user_count)

    def test_03_successful_login(self):
        """3. Успешен login (200 OK, session cookie, работещ GET /api/auth/me/)."""
        user = User.objects.create_user(username="player_two", email="p2@example.com", password="mypassword")
        Profile.objects.create(user=user, nickname="PlayerTwoNick")

        response = self.client.post(self.login_url, {"username": "player_two", "password": "mypassword"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "player_two")
        self.assertIn("sessionid", response.cookies)

        # Subsequent GET /me
        me_response = self.client.get(self.me_url)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "player_two")
        self.assertEqual(me_response.data["profile"]["nickname"], "PlayerTwoNick")

    def test_04_unsuccessful_login(self):
        """4. Неуспешен login (грешна парола -> 400 Bad Request, без session, отказан /me)."""
        user = User.objects.create_user(username="player_three", email="p3@example.com", password="correctpassword")
        Profile.objects.create(user=user, nickname="PlayerThreeNick")

        response = self.client.post(self.login_url, {"username": "player_three", "password": "wrongpassword"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("sessionid", response.cookies)

        # Subsequent GET /me should be denied
        me_response = self.client.get(self.me_url)
        self.assertIn(me_response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_05_permissions_for_me(self):
        """5. Permissions за /me (отказан anonymous, разрешен authenticated, само собствени данни)."""
        # Anonymous
        anon_response = self.client.get(self.me_url)
        self.assertIn(anon_response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Authenticated
        user = User.objects.create_user(username="player_four", email="p4@example.com", password="password123")
        Profile.objects.create(user=user, nickname="PlayerFourNick")
        self.client.force_login(user)

        auth_response = self.client.get(self.me_url)
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_response.data["username"], "player_four")
        self.assertEqual(auth_response.data["profile"]["nickname"], "PlayerFourNick")

    def test_06_profile_update(self):
        """6. Редактиране на профил (nickname, avatar_key запазени; защитени полета недостъпни)."""
        user = User.objects.create_user(username="player_five", email="p5@example.com", password="password123", is_staff=False)
        Profile.objects.create(user=user, nickname="OldNick", avatar_key="knight-1")
        self.client.force_login(user)

        # Successful update
        update_data = {"nickname": "NewNick", "avatar_key": "knight-3"}
        response = self.client.patch(self.me_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["nickname"], "NewNick")
        self.assertEqual(response.data["profile"]["avatar_key"], "knight-3")

        # Database verification
        user.refresh_from_db()
        self.assertEqual(user.profile.nickname, "NewNick")
        self.assertEqual(user.profile.avatar_key, "knight-3")

        # Attempt to modify protected field
        protected_attempt = self.client.patch(self.me_url, {"is_staff": True}, format='json')
        self.assertEqual(protected_attempt.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_07_logout(self):
        """7. Logout (login, 204 logout, прекратена session, отказан последващ /me)."""
        user = User.objects.create_user(username="player_six", email="p6@example.com", password="password123")
        Profile.objects.create(user=user, nickname="PlayerSixNick")

        login_res = self.client.post(self.login_url, {"username": "player_six", "password": "password123"}, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        logout_res = self.client.post(self.logout_url)
        self.assertEqual(logout_res.status_code, status.HTTP_204_NO_CONTENT)

        # Subsequent GET /me
        me_res = self.client.get(self.me_url)
        self.assertIn(me_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_08_csrf_protection(self):
        """8. CSRF (APIClient(enforce_csrf_checks=True): Session-authenticated unsafe заявка без token -> 403 Forbidden, с token -> успех)."""
        csrf_client = APIClient(enforce_csrf_checks=True)
        user = User.objects.create_user(username="player_seven", email="p7@example.com", password="password123")
        Profile.objects.create(user=user, nickname="PlayerSevenNick")

        # Log in the user to establish session
        csrf_client.force_login(user)

        # Get fresh CSRF token for the authenticated session
        csrf_res = csrf_client.get(self.csrf_url)
        self.assertEqual(csrf_res.status_code, status.HTTP_204_NO_CONTENT)
        token = csrf_client.cookies.get('csrftoken').value

        # Session-authenticated unsafe request without token -> 403 Forbidden
        denied_res = csrf_client.patch(
            self.me_url,
            {"nickname": "UpdatedNoCSRF"},
            format='json'
        )
        self.assertEqual(denied_res.status_code, status.HTTP_403_FORBIDDEN)

        # Session-authenticated unsafe request with valid token -> 200 OK
        allowed_res = csrf_client.patch(
            self.me_url,
            {"nickname": "UpdatedWithCSRF"},
            format='json',
            HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(allowed_res.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed_res.data["profile"]["nickname"], "UpdatedWithCSRF")
