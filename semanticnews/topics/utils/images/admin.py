from django.contrib import admin

from .models import TopicImage


@admin.register(TopicImage)
class TopicImageAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at")
    search_fields = ("topic__title",)
    readonly_fields = ("created_at",)
