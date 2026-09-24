import json
from django.test import TestCase, RequestFactory
from django.urls import reverse

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
