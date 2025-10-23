"""Models for storing topic document and webpage links."""

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
        """Return the hostname for the stored URL."""

        return urlparse(self.url).netloc

    @property
    def file_name(self) -> str:
        """Return the trailing file name component of the URL for display."""

        parsed = urlparse(self.url)
        file_name = unquote(PurePosixPath(parsed.path).name)
        if file_name:
            return file_name
        return parsed.netloc or self.url

    @property
    def display_title(self) -> str:
        """Return a user-friendly name for the document."""

        return self.title or self.file_name

    def save(self, *args, **kwargs):
        """Guess the document type from the URL before saving."""

        self.document_type = self._guess_document_type()
        super().save(*args, **kwargs)

    def _guess_document_type(self) -> str:
        """Infer the document type from the URL extension."""

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
        """Return the hostname for the stored URL."""

        return urlparse(self.url).netloc
