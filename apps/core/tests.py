from django.core.management import call_command
from django.test import TestCase

from apps.core.models import AppConstants


class ConstantsTests(TestCase):
    def test_init_constants_seeds_defaults(self):
        call_command("init_constants")
        self.assertEqual(AppConstants.get("vehicle_range_miles"), "500")
        self.assertEqual(AppConstants.get("miles_per_gallon"), "10")

    def test_init_constants_is_idempotent(self):
        call_command("init_constants")
        count = AppConstants.objects.count()
        call_command("init_constants")
        self.assertEqual(AppConstants.objects.count(), count)

    def test_get_returns_default_for_missing_key(self):
        self.assertIsNone(AppConstants.get("does_not_exist"))
        self.assertEqual(AppConstants.get("does_not_exist", "fallback"), "fallback")
