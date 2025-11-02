from django.contrib import admin

from .models import Widget, WidgetAPIExecution


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_at")
    search_fields = ("name", "prompt_template")
    ordering = ("name",)


@admin.register(WidgetAPIExecution)
class WidgetAPIExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "widget",
        "topic",
        "section",
        "status",
        "created_at",
        "completed_at",
    )
    search_fields = ("widget__name", "widget_type")
    list_filter = ("status", "widget_type")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "prompt_context",
        "prompt_text",
        "extra_instructions",
        "raw_response",
        "parsed_response",
        "metadata",
    )
    raw_id_fields = ("widget", "topic", "section", "user")
