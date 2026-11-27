"""
行旅识景 TripScape / apps/core/tests

core tests。
"""

from django.test import TestCase


class HealthTests(TestCase):
    def test_healthz(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)

    def test_readyz(self):
        resp = self.client.get("/readyz")
        self.assertEqual(resp.status_code, 200)
