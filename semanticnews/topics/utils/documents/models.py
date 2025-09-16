"""Models for storing topic document and webpage links."""

from urllib.parse import urlparse

from django.conf import settings
from django.db import models


class TopicLinkBase(models.Model):
    """Abstract base model for links associated with a topic."""

    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self) -> str:  # pragma: no cover - trivial string representation
        return self.title or self.url

    @property
    def domain(self) -> str:
        """Return the hostname for the stored URL."""

        return urlparse(self.url).netloc


class TopicDocumentLink(TopicLinkBase):
    """Link to an external document relevant to the topic."""

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
        default_related_name = 'document_links'
        verbose_name = 'Document link'
        verbose_name_plural = 'Document links'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['document_type']),
        ]

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


class TopicWebpageLink(TopicLinkBase):
    """Link to an external webpage relevant to the topic."""

    class Meta:
        app_label = 'topics'
        default_related_name = 'webpage_links'
        verbose_name = 'Webpage link'
        verbose_name_plural = 'Webpage links'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['created_at']),
        ]
