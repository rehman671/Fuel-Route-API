from django.db import models


class AppConstants(models.Model):
    """
    Generic key/value store for the tunable constants used across the project
    (vehicle assumptions, planner tuning, external service URLs, …).

    Keeping these in the database instead of hard-coding them in services.py
    lets them be changed via the admin without a redeploy.

    Seed / refresh the defaults with:  ``python manage.py init_constants``
    Read a value with:                 ``AppConstants.get("vehicle_range_miles")``
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)

    class Meta:
        verbose_name = "App constant"
        verbose_name_plural = "App constants"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=None):
        """Return the stored value for ``key`` (as a string), or ``default``."""
        row = cls.objects.filter(key=key).first()
        return row.value if row else default
