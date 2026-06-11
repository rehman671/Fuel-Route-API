from django.contrib import admin

from apps.core.models import AppConstants


@admin.register(AppConstants)
class AppConstantsAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)
    ordering = ("key",)
