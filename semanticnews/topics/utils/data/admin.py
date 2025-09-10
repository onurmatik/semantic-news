from django.contrib import admin

from .models import TopicData, TopicDataInsight


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
