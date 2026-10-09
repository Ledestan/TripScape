"""行旅识景 TripScape
创建日期：2025-09-01

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
