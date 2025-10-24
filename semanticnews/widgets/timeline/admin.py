from django.contrib import admin

from .models import TopicEvent


@admin.register(TopicEvent)
class TopicEventAdmin(admin.ModelAdmin):
    list_display = ("topic", "event", "source", "relevance", "significance")
    list_filter = ("source", "significance")
    search_fields = ("topic__title", "event__title")
