# Test login and security functionality
from django.contrib.auth.hashers import check_password, make_password
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class TestAuthRegister(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            email="testuser@test.edu.co",
            password_hash=make_password("securepassword123"),
        )
        self.login_url = reverse("auth-login")

    def test_login_success(self):
        data = {"email": "testuser@test.edu.co", "password": "securepassword123"}
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_login_invalid_credentials(self):
        data = {"email": "testuser@test.edu.co", "password": "wrongpassword"}
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
