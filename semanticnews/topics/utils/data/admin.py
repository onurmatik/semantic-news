from django.contrib import admin
from django.db import models
from django.forms import Textarea

from .models import TopicData, TopicDataInsight, TopicDataVisualization, TopicDataRequest


@admin.register(TopicDataRequest)
class TopicDataRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "user", "mode", "status", "short_task_id", "has_saved", "created_at", "saved_at", "updated_at")
    list_filter = ("mode", "status", ("saved_data", admin.EmptyFieldListFilter), "created_at", "updated_at", "saved_at")
    search_fields = ("topic__title", "user__username", "task_id")
    readonly_fields = ("created_at", "updated_at", "saved_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("topic", "user", "saved_data")
    autocomplete_fields = ("topic", "user", "saved_data")

    formfield_overrides = {
        models.JSONField: {"widget": Textarea(attrs={"rows": 12, "style": "font-family: monospace"})},
    }

    fieldsets = (
        (None, {
            "fields": ("topic", "user", "mode", "status", "task_id"),
        }),
        ("Payload & Result", {
            "fields": ("input_payload", "result", "error_message"),
            "classes": ("collapse",),
        }),
        ("Persistence", {
            "fields": ("saved_data", "saved_at"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def short_task_id(self, obj):
        return (obj.task_id[:10] + "…") if obj.task_id and len(obj.task_id) > 10 else (obj.task_id or "—")
    short_task_id.short_description = "Task ID"

    def has_saved(self, obj):
        return bool(obj.saved_data_id)
    has_saved.boolean = True
    has_saved.short_description = "Saved"


@admin.register(TopicData)
class TopicDataAdmin(admin.ModelAdmin):
    list_display = ("topic", "name", "url", "created_at")
    search_fields = ("topic__title", "name", "url")
    readonly_fields = ("created_at",)


@admin.register(TopicDataInsight)
class TopicDataInsightAdmin(admin.ModelAdmin):
    list_display = ("topic", "insight")
    search_fields = ("topic", "insight")
    readonly_fields = ("created_at",)


@admin.register(TopicDataVisualization)
class TopicDataVisualizationAdmin(admin.ModelAdmin):
    list_display = ("topic", "insight", "chart_type")
    list_filter = ("chart_type",)
    readonly_fields = ("created_at",)
