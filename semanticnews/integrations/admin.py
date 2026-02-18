from django.contrib import admin

from .models import ExternalTopicConnection


@admin.register(ExternalTopicConnection)
class ExternalTopicConnectionAdmin(admin.ModelAdmin):
    list_display = ("provider", "topic", "external_topic_id", "updated_at")
    search_fields = ("external_topic_id", "display_name", "query", "topic__title")
    list_filter = ("provider",)
