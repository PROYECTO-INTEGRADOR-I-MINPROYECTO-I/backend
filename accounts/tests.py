import time

from django.contrib.auth.hashers import make_password
from django.test import override_settings
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
