import json
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.db import connection

from event.views import test

class TestViewTestCase(TestCase):
    def test_view_returns_working_message(self):
        # 1. Simulate a GET request to the view endpoint
        factory = RequestFactory()
        request = factory.get("/test/")

        # 2. Call the view function
        response = test(request)

        # 3. Assert status code and JSON content
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content), 
            {"message": "Server is working!"}
        )

    def test2(self):
        self.assertEqual(1 + 1, 2)

    def test_database_connection(self):
        """Directly test that the test database is connected and responding."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            # If the database is connected, SELECT 1 returns a tuple (1,)
            self.assertEqual(result, (1,))
        except Exception as e:
            self.fail(f"Database connection failed with error: {e}")

