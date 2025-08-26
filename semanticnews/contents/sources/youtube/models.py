from datetime import datetime, timedelta, timezone

from django.urls import reverse
from django.utils.functional import cached_property
from django.utils import timezone as django_timezone
from django.db import models, transaction
from django.conf import settings
from googleapiclient.discovery import build
from pgvector.django import VectorField
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from semanticnews.openai import OpenAI

from ..youtube.utils import list_youtube_transcripts


MAX_VIDEO_RESULTS = 5  # Max videos to fetch at once from a channel


class Channel(models.Model):
    handle = models.CharField(max_length=50)
    default_language = models.CharField(max_length=5, default='tr')

    # Set by save() initially
    channel_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    uploads_playlist_id = models.CharField(max_length=50, blank=True, null=True)  # Remove? Can be derived from channel_id

    # Updated by update_channel_info()
    title = models.CharField(max_length=200, blank=True)
    thumbnail = models.URLField(blank=True, null=True)  # Download?

    channel_last_update = models.DateTimeField(blank=True, null=True)
    channel_next_update = models.DateTimeField(default=django_timezone.now)

    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def save(self, **kwargs):
        update_details = False
        if not self.channel_id:
            update_details = True
            youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
            channel_response = youtube.channels().list(
                part="contentDetails",
                forHandle=self.handle,
            ).execute()
            self.channel_id = channel_response["items"][0]["id"]
            self.uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        super().save(**kwargs)
        if update_details:
            self.update_channel_info()

    def update_channel_info(self):
        youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
        channel_response = youtube.channels().list(
            part="snippet",
            id=self.channel_id,
        ).execute()
        self.title = channel_response["items"][0]["snippet"]["title"]
        self.thumbnail = channel_response["items"][0]["snippet"]["thumbnails"]["medium"]["url"]
        self.save()

    def fetch_channel_content(self):
        youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)

        # Fetch new videos
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=self.uploads_playlist_id,
            maxResults=MAX_VIDEO_RESULTS,
        ).execute()
        for item in playlist_response.get("items", []):
            snippet = item["snippet"]
            Video.objects.get_or_create(
                video_id=item["snippet"]["resourceId"]["videoId"],
                defaults={
                    'channel': self,
                    'title': snippet["title"],
                    'description': snippet["description"],
                    'thumbnail': snippet["thumbnails"]["medium"]["url"],
                    'published_at': datetime.strptime(
                        snippet["publishedAt"],
                        "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc),
                }
            )

        now = django_timezone.now()
        self.channel_last_update = now
        # TODO: smarter, dynamic update period calculation
        self.channel_next_update = now + timedelta(minutes=60)
        self.save()


class Video(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, blank=True, null=True)
    video_id = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    thumbnail = models.URLField(blank=True, null=True)
    published_at = models.DateTimeField(db_index=True)
    added_at = models.DateTimeField(auto_now_add=True)

    is_short = models.BooleanField(default=False)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def save(self, **kwargs):
        super().save(**kwargs)
        # If transcript is missing, enqueue task
        if not VideoTranscript.objects.filter(video=self).exists():
            from .tasks import fetch_transcript
            fetch_transcript.delay_on_commit(self.pk)

    def get_absolute_url(self):
        return reverse('video_detail', kwargs={'video_id': self.video_id})

    @cached_property
    def get_video_url(self):
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def get_embed_url(self):
        return f"https://www.youtube.com/embed/{self.video_id}"

    def fetch_transcript(self):
        """Fetch and store the transcript for the video in the database."""
        default_language = self.channel and self.channel.default_language or 'tr'
        try:
            transcript_list = list_youtube_transcripts(self.video_id)
        except TranscriptsDisabled:
            print(f"Transcripts are disabled for video {self.video_id}")
            return None
        except Exception as e:
            print(f"Error fetching transcripts for {self.video_id}: {e}")
            return None

        # Check if the default language is available
        available_languages = {t.language_code for t in transcript_list}
        default_language_available = default_language in available_languages

        for t in transcript_list:
            if t.language_code == default_language or not default_language_available:
                try:
                    transcript_data = t.fetch()

                except Exception as e:
                    print(f"Error fetching transcript for {self.video_id} ({t.language_code}): {e}")
                    return None

                else:
                    VideoTranscript.objects.update_or_create(
                        video=self,
                        defaults={
                            "transcript_data": transcript_data.to_raw_data(),
                            "language_code": t.language_code,
                            "is_generated": t.is_generated,
                        },
                    )


class VideoTranscript(models.Model):
    video = models.OneToOneField(Video, on_delete=models.CASCADE)
    updated = models.DateTimeField(auto_now=True)

    # The raw transcript data populated by Video.fetch_transcript()
    transcript_data = models.JSONField(default=dict, blank=True)  # [{"text": "...", "start": 0.0, "duration": 10.0}, ]
    language_code = models.CharField(max_length=10)
    is_generated = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["video", "language_code"], name="unique_video_language")
        ]

    def __str__(self):
        return f"{self.video.title} transcript"

    def save(self, **kwargs):
        super().save(**kwargs)
        # If transcript is not chunked yet, enqueue task
        if not VideoTranscriptChunk.objects.filter(transcript=self).exists():
            from .tasks import create_transcript_chunks
            create_transcript_chunks.delay_on_commit(self.pk)

    def get_non_overlapping_chunks(self, overlap=1000):
        """Return transcript chunks with the leading overlap removed."""
        cleaned = []
        for i, chunk in enumerate(self.chunks.all()):
            text = chunk.revised_text or ""
            if i > 0:
                text = text[overlap:]
            cleaned.append({"start_time": chunk.start_time, "text": text})
        return cleaned

    @property
    def revised_transcript(self) -> str:
        """Concatenate all revised chunks dropping overlaps."""
        return "".join(c["text"] for c in self.get_non_overlapping_chunks())

    def create_chunks(self, size=3000, overlap=1000):
        # Clear existing chunks to avoid duplicates when re-running.
        self.chunks.all().delete()

        # Concatenate all transcript segments and record the mapping between
        # text indices and the segment's start time.
        overall_text = ""
        mapping = []  # list of tuples: (text_index, segment_start_time)
        for segment in self.transcript_data:
            mapping.append((len(overall_text), segment["start"]))
            overall_text += ' ' + segment["text"]

        # Create chunks with given size and overlapping
        chunk_start = 0
        while chunk_start < len(overall_text):
            # Slice out a chunk of text
            chunk_text = overall_text[chunk_start:chunk_start + size]

            # Determine the start_time of the chunk.
            # We choose the start time of the last transcript segment that started at or before chunk_start.
            start_time = 0.0
            for index, seg_start in reversed(mapping):
                if index <= chunk_start:
                    start_time = seg_start
                    break

            # Create the VideoTranscriptChunk object.
            VideoTranscriptChunk.objects.create(
                transcript=self,
                start_time=int(start_time),
                raw_text=chunk_text
            )

            # Move the start forward, allowing for the specified overlap.
            # (size - overlap) determines the shift so that each new chunk overlaps the previous chunk.
            chunk_start += (size - overlap)


class VideoTranscriptChunk(models.Model):
    transcript = models.ForeignKey(VideoTranscript, on_delete=models.CASCADE, related_name='chunks')
    start_time = models.PositiveIntegerField(help_text="Start time in seconds")
    raw_text = models.TextField(help_text="The raw text content of the chunk")
    revised_text = models.TextField(blank=True, null=True, help_text="The revised text content of the chunk")

    def __str__(self):
        return f"{self.transcript.video}::{self.start_time}"

    class Meta:
        ordering = ("start_time",)

    def save(self, **kwargs):
        if self.revised_text and (self.embedding is None or len(self.embedding) == 0):
            self.embedding = self.get_embedding()

        super().save(**kwargs)

        if self.raw_text and not self.revised_text:
            # If the chunk is not revised yet, enqueue task
            from .tasks import revise_chunk_text  # lazy import

            # Schedule the Celery task after transaction is committed
            transaction.on_commit(lambda: revise_chunk_text.delay(self.pk))

    def get_video_url(self):
        return f"https://www.youtube.com/watch?v={self.transcript.video.video_id}&t={self.start_time}s"

    def get_embed_url(self):
        return f"https://www.youtube.com/embed/{self.transcript.video.video_id}?start={self.start_time}"

    @property
    def source_name(self) -> str:
        """
        Channel identifier used by diversify(); channel_id is unique, cheap to compare.
        """
        return self.transcript.video.channel_id

    def get_embedding(self):
        if self.revised_text and (self.embedding is None or len(self.embedding) == 0):
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.revised_text,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    def revise_text(self):
        # Revise the raw text; embeddings are based on the revised version

        client = OpenAI()

        if not self.revised_text and self.raw_text:
            # Revise the raw text to fix typos & punctuation
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # <= best model loyal to the instruction
                messages=[
                    {
                        "role": "system",
                        "content": "The provided text is a chunk of a video transcript. "
                                   "Revise it by adding appropriate punctuation and correcting grammar and typos. "
                                   "Remove premature sentences from the start and the end of the chunk, if any. "
                                   "Remove filler sounds. Give paragraph breaks where appropriate. "
                                   "Preserve the original meaning and structure. "
                                   "Do not shorten, summarize, or remove any content."
                    },
                    {
                        "role": "user",
                        "content": self.raw_text,
                    },
                ],
            )
            self.revised_text = response.choices[0].message.content

        self.save()
