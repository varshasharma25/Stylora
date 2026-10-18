from django.test import TestCase, Client
from django.urls import reverse


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_returns_healthy(self):
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('app'), 'Stylora')
        self.assertEqual(data.get('tagline'), 'Your wardrobe, styled.')
