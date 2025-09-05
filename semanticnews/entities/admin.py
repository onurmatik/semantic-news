from django.contrib import admin
from .models import Entity


@admin.register(Entity)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name", "disambiguation", "slug", "created_at")
    search_fields = ("name", "disambiguation", "slug")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
