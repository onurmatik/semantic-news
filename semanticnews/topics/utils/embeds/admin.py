from django.contrib import admin

from .models import TopicTweet, TopicYoutubeVideo


@admin.register(TopicTweet)
class TopicTweetAdmin(admin.ModelAdmin):
    list_display = ('topic', 'tweet_id', 'url', 'created_at')
    search_fields = ('url',)


@admin.register(TopicYoutubeVideo)
class TopicYoutubeVideoAdmin(admin.ModelAdmin):
    list_display = ('topic', 'title', 'video_id', 'status', 'created_at')
    search_fields = ('title', 'video_id')
