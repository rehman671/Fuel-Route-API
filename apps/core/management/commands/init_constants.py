"""
Management command: init_constants
==================================
Seeds the AppConstants key/value table with the project's default constants.

Run once after migrations (the Docker entrypoint does this automatically):
    python manage.py init_constants

Idempotent — existing keys are left untouched unless --reset is passed.

Options:
    --reset     Overwrite existing keys with the default values below.
"""

from django.core.management.base import BaseCommand

from apps.core.models import AppConstants

# ── Default constants ────────────────────────────────────────────────────────
# (values are stored as strings; callers cast as needed)
DEFAULTS = {
    # Vehicle assumptions
    "vehicle_range_miles": "500",
    "miles_per_gallon": "10",
    "default_fuel_price": "3.50",
    # External services
    "nominatim_url": "https://nominatim.openstreetmap.org/search",
    "osrm_route_url": "https://router.project-osrm.org/route/v1/driving",
    "user_agent": "FuelRouteAPI/1.0 (assessment project)",
}


class Command(BaseCommand):
    help = "Seed the AppConstants table with the project's default constants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Overwrite existing constants with the default values.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        created, updated, skipped = 0, 0, 0

        for key, value in DEFAULTS.items():
            obj, was_created = AppConstants.objects.get_or_create(
                key=key, defaults={"value": value}
            )
            if was_created:
                created += 1
            elif reset and obj.value != value:
                obj.value = value
                obj.save(update_fields=["value"])
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Constants ready — {created} created, {updated} updated, {skipped} unchanged."
        ))
