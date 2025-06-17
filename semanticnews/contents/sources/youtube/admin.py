import csv

from asgiref.sync import async_to_sync
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from .models import Channel, Video, VideoTranscript, VideoTranscriptChunk


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("title", "handle", "channel_id", "active")
    list_editable = ("active",)
    search_fields = ("title", "handle", "channel_id")

    actions = ["update_channel_info", "fetch_channel_content"]

    def update_channel_info(self, request, queryset):
        """Fetch latest videos for the selected channels"""
        for channel in queryset:
            channel.update_channel_info()
        self.message_user(request, f"{queryset.count()} channel(s) updated.")

    def fetch_channel_content(self, request, queryset):
        """Fetch latest videos for the selected channels"""
        for channel in queryset:
            channel.fetch_channel_content()
        self.message_user(request, f"{queryset.count()} channel(s) updated.")


class TranscriptFetchedFilter(admin.SimpleListFilter):
    title = 'Transcript'  # Display title
    parameter_name = 'transcript_fetched'  # URL query param

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Fetched'),
            ('no', 'Not fetched'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.filter(videotranscript__isnull=False)
        if value == 'no':
            return queryset.filter(videotranscript__isnull=True)
        return queryset


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "channel", "video_id", "published_at", "added_at", "transcript_fetched")
    search_fields = ("title", "video_id", "channel__title")
    list_filter = ("channel", "published_at", "is_short", TranscriptFetchedFilter)

    actions = ["fetch_transcripts", "force_fetch_video_stats", "fetch_due_video_stats"]

    def transcript_fetched(self, obj):
        return hasattr(obj, 'videotranscript')
    transcript_fetched.boolean = True

    def fetch_transcripts(self, request, queryset):
        """Fetch and store transcripts for selected videos"""
        for video in queryset:
            try:
                video.fetch_transcript()
            except Exception as e:
                self.message_user(request, f"Error fetching transcript for {video.title}: {str(e)}", level="error")

        self.message_user(request, f"Transcripts updated for {queryset.count()} video(s).")


@admin.register(VideoTranscript)
class VideoTranscriptAdmin(admin.ModelAdmin):
    list_display = ("video", "updated")
    search_fields = ("video__title", "video__video_id")
    list_filter = ("updated",)
    actions = ['create_chunks']

    def create_chunks(self, request, queryset):
        """Create the TranscriptChunk instances"""
        for transcript in queryset:
            try:
                async_to_sync(transcript.create_chunks)()
            except Exception as e:
                self.message_user(request, f"Error creating chunks: {str(e)}", level="error")

        self.message_user(request, f"Chunks created.")


@admin.register(VideoTranscriptChunk)
class VideoTranscriptChunkAdmin(admin.ModelAdmin):
    list_display = ("transcript", "start_time", "transcript__video__added_at")
