from django.contrib import admin

from .models import Widget


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_at")
    search_fields = ("name", "prompt_template")
    ordering = ("name",)
