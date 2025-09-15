from django.contrib import admin

from .models import TopicMedia


@admin.register(TopicMedia)
class TopicMediaAdmin(admin.ModelAdmin):
    list_display = ("topic", "media_type", "url", "created_at")
    search_fields = ("topic__title", "url")
    list_filter = ("media_type",)
