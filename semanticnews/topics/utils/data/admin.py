from django.contrib import admin

from .models import TopicData


@admin.register(TopicData)
class TopicDataAdmin(admin.ModelAdmin):
    list_display = ("topic", "url", "created_at")
    search_fields = ("topic__title", "url")
    readonly_fields = ("created_at",)
