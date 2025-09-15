from django.contrib import admin

from .models import TopicYoutubeVideo, TopicVimeoVideo


@admin.register(TopicYoutubeVideo)
class TopicYoutubeVideoAdmin(admin.ModelAdmin):
    list_display = ("topic", "url", "title", "created_at")
    search_fields = ("topic__title", "url", "title")


@admin.register(TopicVimeoVideo)
class TopicVimeoVideoAdmin(admin.ModelAdmin):
    list_display = ("topic", "url", "title", "created_at")
    search_fields = ("topic__title", "url", "title")
