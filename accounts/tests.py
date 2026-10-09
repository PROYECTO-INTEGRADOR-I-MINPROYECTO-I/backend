import time

from django.contrib.auth.hashers import check_password, make_password
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from event.models import Event

from .models import User
from .tokens import issue_tokens

PASSWORD = "clave-segura-123"
FRONT_ORIGIN = "http://localhost:5173"


@override_settings(CORS_ALLOWED_ORIGINS=[FRONT_ORIGIN])
class JWTAuthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            name="Ana", email="ana@example.com", password_hash=make_password(PASSWORD)
        )

    def login(self, email="ana@example.com", password=PASSWORD):
        return self.client.post(
            "/api/auth/login/", {"email": email, "password": password}, format="json"
        )

    def bearer(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_login_returns_access_and_httponly_refresh_cookie(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["email"], "ana@example.com")
        self.assertIn("access", response.data)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/auth/")

    def test_wrong_password_and_unknown_email_get_the_same_401(self):
        wrong_password = self.login(password="otra-clave-123")
        unknown_email = self.login(email="nadie@example.com")

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_email.status_code, 401)
        self.assertEqual(wrong_password.json(), unknown_email.json())

    def test_private_endpoint_requires_a_valid_bearer(self):
        access = self.login().data["access"]

        self.assertEqual(self.client.get("/api/eventos/").status_code, 401)

        self.bearer(access)
        self.assertEqual(self.client.get("/api/eventos/").status_code, 200)

        self.bearer(access[:-2] + "xx")  # tampered signature
        self.assertEqual(self.client.get("/api/eventos/").status_code, 401)

    def test_refresh_token_is_not_accepted_as_bearer(self):
        refresh, _ = issue_tokens(self.user)
        self.bearer(refresh)

        self.assertEqual(self.client.get("/api/eventos/").status_code, 401)

    def test_access_token_is_not_accepted_as_refresh_cookie(self):
        _, access = issue_tokens(self.user)
        self.client.cookies["refresh_token"] = access

        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_refresh_rotates_cookie_and_returns_new_access(self):
        self.login()

        response = self.client.post("/api/auth/refresh/", HTTP_ORIGIN=FRONT_ORIGIN)

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh_token", response.cookies)

    def test_refresh_without_cookie_is_401(self):
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_refresh_from_foreign_origin_is_403(self):
        self.login()

        for origin in ("https://evil.example", "null"):
            response = self.client.post("/api/auth/refresh/", HTTP_ORIGIN=origin)
            self.assertEqual(response.status_code, 403, origin)

    def test_logout_revokes_access_and_refresh(self):
        access = self.login().data["access"]
        old_refresh = self.client.cookies["refresh_token"].value

        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)

        self.bearer(access)
        self.assertEqual(self.client.get("/api/eventos/").status_code, 401)
        self.client.credentials()
        self.client.cookies["refresh_token"] = old_refresh
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_logout_with_only_bearer_also_revokes(self):
        access = self.login().data["access"]
        self.client.cookies.clear()
        self.bearer(access)

        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/eventos/").status_code, 401)

    def test_session_older_than_cap_cannot_refresh(self):
        expired_login = time.time() - 31 * 86400
        refresh, _ = issue_tokens(self.user, auth_time=expired_login)
        self.client.cookies["refresh_token"] = refresh

        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_other_organizer_gets_404_on_my_event(self):
        event = Event.objects.create(user=self.user, name="Boda", due_date="2099-01-01T18:00:00Z")
        intruder = User.objects.create(
            name="Beto", email="beto@example.com", password_hash=make_password(PASSWORD)
        )
        _, intruder_access = issue_tokens(intruder)
        self.bearer(intruder_access)

        url = f"/api/eventos/{event.pk}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

class TestRegister(APITestCase):
    def setUp(self):
        self.register_url = reverse("auth-register")
        self.valid_payload = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "name": "Eduardo Testeo Si Esto Falla Me Meo",
        }

    def test_registration_success(self):
        """Verify user is created in DB with a hashed password."""
        response = self.client.post(
            self.register_url, self.valid_payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 1. Assert user now exists in the database
        user = User.objects.filter(email="newuser@example.com").first()
        self.assertIsNotNone(user)

        # 2. Assert password was hashed properly and not saved in plaintext
        self.assertNotEqual(user.password_hash, "securepassword123")
        self.assertTrue(check_password("securepassword123", user.password_hash))

    def test_registration_duplicate_email(self):
        """Verify registration fails if email already exists."""
        # Create existing user
        User.objects.create(
            email="newuser@example.com", password_hash=make_password("somehash")
        )

        response = self.client.post(
            self.register_url, self.valid_payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_missing_email(self):
        """Verify validation error when email is missing."""
        payload = {"password": "securepassword123"}
        response = self.client.post(self.register_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["error"]["details"])
        self.assertIn("Escribe tu correo.", response.data["error"]["details"]["email"])

    def test_registration_missing_password(self):
        """Verify validation error when password is missing."""
        payload = {"email": "newuser@example.com"}
        response = self.client.post(self.register_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data["error"]["details"])
        self.assertIn(
            "Escribe tu contraseña.", response.data["error"]["details"]["password"]
        )


class UserSettingsTests(APITestCase):
    url = "/api/user/settings/"
    limit_message = "El límite debe estar entre 1 y 16 horas"

    def make_user(self, email="ana@example.com"):
        return User.objects.create(
            name="Ana", email=email, password_hash=make_password(PASSWORD)
        )

    def auth(self, user):
        _refresh, access = issue_tokens(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_new_user_defaults_to_six_hours(self):
        user = self.make_user()
        self.auth(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"max_daily_hours": "6.00"})

    def test_out_of_range_values_are_rejected(self):
        user = self.make_user()
        self.auth(user)

        for value in (0, 0.5, 16.5, 17):
            for method in (self.client.put, self.client.patch):
                response = method(self.url, {"max_daily_hours": value}, format="json")
                self.assertEqual(response.status_code, 400, value)
                self.assertEqual(
                    response.json()["error"]["details"]["max_daily_hours"],
                    [self.limit_message],
                    value,
                )

        user.refresh_from_db()
        self.assertEqual(float(user.max_daily_hours), 6.0)

    def test_non_numeric_value_is_rejected(self):
        self.auth(self.make_user())

        response = self.client.put(self.url, {"max_daily_hours": "abc"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["details"]["max_daily_hours"], ["El límite debe ser un número válido."]
        )

    def test_boundary_values_are_accepted_and_persisted(self):
        user = self.make_user()
        self.auth(user)

        for value, expected in ((1, "1.00"), (16, "16.00")):
            response = self.client.put(self.url, {"max_daily_hours": value}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"max_daily_hours": expected})
            user.refresh_from_db()
            self.assertEqual(str(user.max_daily_hours), expected)

    def test_each_organizer_keeps_their_own_limit(self):
        user_a = self.make_user("a@example.com")
        user_b = self.make_user("b@example.com")

        self.auth(user_a)
        self.client.patch(self.url, {"max_daily_hours": 3}, format="json")
        self.auth(user_b)
        self.client.patch(self.url, {"max_daily_hours": 10}, format="json")

        self.auth(user_a)
        self.assertEqual(self.client.get(self.url).json(), {"max_daily_hours": "3.00"})
        self.auth(user_b)
        self.assertEqual(self.client.get(self.url).json(), {"max_daily_hours": "10.00"})

    def test_extra_fields_are_ignored(self):
        user = self.make_user()
        self.auth(user)

        response = self.client.patch(
            self.url,
            {"max_daily_hours": 8, "email": "hack@example.com", "name": "Otro", "token_version": 99},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"max_daily_hours": "8.00"})
        user.refresh_from_db()
        self.assertEqual(user.email, "ana@example.com")
        self.assertEqual(user.name, "Ana")
        self.assertEqual(user.token_version, 0)

    def test_decimal_limit_and_missing_field(self):
        user = self.make_user()
        self.auth(user)

        response = self.client.patch(self.url, {"max_daily_hours": 7.5}, format="json")
        self.assertEqual(response.json(), {"max_daily_hours": "7.50"})

        response = self.client.put(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.put(self.url, {"max_daily_hours": 8}, format="json").status_code, 401
        )
        self.assertEqual(
            self.client.patch(self.url, {"max_daily_hours": 8}, format="json").status_code, 401
        )
