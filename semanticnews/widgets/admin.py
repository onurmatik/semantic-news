from django.contrib import admin

from .models import Widget, WidgetActionExecution


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "prompt_template")
    ordering = ("name",)

