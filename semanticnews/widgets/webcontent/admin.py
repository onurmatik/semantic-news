"""Admin registrations for web content widgets."""

from django.contrib import admin

from .models import TopicDocument, TopicTweet, TopicWebpage, TopicYoutubeVideo


@admin.register(TopicDocument)
class TopicDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'topic',
        'document_type',
        'domain',
        'created_by',
        'created_at',
    )
    list_filter = ('document_type', 'created_at')
    search_fields = ('title', 'topic__title', 'url')
    readonly_fields = ('created_at',)
    raw_id_fields = ('topic', 'created_by')


@admin.register(TopicWebpage)
class TopicWebpageAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'topic',
        'domain',
        'created_by',
        'created_at',
    )
    list_filter = ('created_at',)
    search_fields = ('title', 'topic__title', 'url')
    readonly_fields = ('created_at',)
    raw_id_fields = ('topic', 'created_by')


@admin.register(TopicTweet)
class TopicTweetAdmin(admin.ModelAdmin):
    list_display = ('topic', 'tweet_id', 'url', 'created_at')
    search_fields = ('url',)


@admin.register(TopicYoutubeVideo)
class TopicYoutubeVideoAdmin(admin.ModelAdmin):
    list_display = ('topic', 'title', 'video_id', 'status', 'created_at')
    search_fields = ('title', 'video_id')
