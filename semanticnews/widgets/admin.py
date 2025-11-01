from django.contrib import admin

from .models import Widget


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "updated_at")
    search_fields = ("name", "prompt")
    list_filter = ("type",)
    ordering = ("name",)
