from django.contrib import admin

from .models import TopicSocialEmbed, TopicYoutubeVideo


@admin.register(TopicSocialEmbed)
class TopicSocialEmbedAdmin(admin.ModelAdmin):
    list_display = ('topic', 'provider', 'url', 'created_at')
    search_fields = ('url',)


@admin.register(TopicYoutubeVideo)
class TopicYoutubeVideoAdmin(admin.ModelAdmin):
    list_display = ('topic', 'title', 'video_id', 'status', 'created_at')
    search_fields = ('title', 'video_id')
