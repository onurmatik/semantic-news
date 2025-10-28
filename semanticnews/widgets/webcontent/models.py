"""Models for storing links to external web content associated with topics."""

from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.db import models


class TopicDocument(models.Model):
    """Link to an external document relevant to the topic."""

    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    DOCUMENT_TYPES = [
        ("pdf", "PDF"),
        ("doc", "DOC"),
        ("docx", "DOCX"),
        ("ppt", "PowerPoint"),
        ("xls", "Spreadsheet"),
        ("txt", "Text"),
        ("other", "Other"),
    ]

    EXTENSION_TYPE_MAP = {
        '.pdf': 'pdf',
        '.doc': 'doc',
        '.docx': 'docx',
        '.ppt': 'ppt',
        '.pptx': 'ppt',
        '.xls': 'xls',
        '.xlsx': 'xls',
        '.txt': 'txt',
    }

    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        default='other',
    )

    class Meta:
        app_label = 'topics'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial string representation
        return self.title or self.url

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc

    @property
    def file_name(self) -> str:
        parsed = urlparse(self.url)
        file_name = unquote(PurePosixPath(parsed.path).name)
        if file_name:
            return file_name
        return parsed.netloc or self.url

    @property
    def display_title(self) -> str:
        return self.title or self.file_name

    def save(self, *args, **kwargs):
        self.document_type = self._guess_document_type()
        super().save(*args, **kwargs)

    def _guess_document_type(self) -> str:
        path = urlparse(self.url).path.lower()
        for extension, doc_type in self.EXTENSION_TYPE_MAP.items():
            if path.endswith(extension):
                return doc_type
        return 'other'


class TopicWebpage(models.Model):
    """Link to an external webpage relevant to the topic."""

    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='webpages',
    )
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        app_label = 'topics'
        verbose_name = 'Webpage'
        verbose_name_plural = 'Webpages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial string representation
        return self.title or self.url

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc


class TopicTweet(models.Model):
    """Embedded tweet linked to a topic."""

    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='tweets'
    )
    tweet_id = models.CharField(max_length=50, db_index=True)
    url = models.URLField()
    html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        app_label = 'topics'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "tweet_id"), name="unique_topic_tweet"
            )
        ]

    def __str__(self):  # pragma: no cover - trivial string representation
        return f"Tweet {self.tweet_id} for {self.topic.title}"


class TopicYoutubeVideo(models.Model):
    """Embedded YouTube video linked to a topic."""

    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='youtube_videos')
    url = models.URLField(blank=True, null=True)
    video_id = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    thumbnail = models.URLField(blank=True, null=True)
    video_published_at = models.DateTimeField(db_index=True, blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In progress"),
            ("finished", "Finished"),
            ("error", "Error"),
        ],
        default="in_progress",
    )
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(blank=True, null=True, max_length=20)

    class Meta:
        app_label = 'topics'

    def __str__(self):  # pragma: no cover - trivial string representation
        return f"{self.title} for {self.topic.title}"
