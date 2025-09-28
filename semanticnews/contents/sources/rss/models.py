from urllib.parse import urlparse, urlunparse
from datetime import datetime

import requests
import feedparser
from semanticnews.openai import OpenAI, AsyncOpenAI

from django.utils.html import strip_tags
from django.db import models
from pgvector.django import VectorField, L2Distance, HnswIndex


class RssFeed(models.Model):
    url = models.URLField(unique=True)
    title = models.CharField(max_length=20, blank=True, null=True)
    active = models.BooleanField(default=True)

    last_fetch = models.DateTimeField(auto_now=True)
    last_fetch_error = models.CharField(max_length=500, blank=True, null=True)
    consecutive_error_count = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        if self.title:
            return self.title
        else:
            parsed_url = urlparse(self.url)
            domain = parsed_url.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain

    def save(self, *args, **kwargs):
        # If instance exists, fetch its previous active state
        if self.pk:
            previous = self.__class__.objects.get(pk=self.pk)
            # If active changed from False to True, reset consecutive_error_count
            if not previous.active and self.active:
                self.consecutive_error_count = 0

        # Deactivate if too many errors
        if self.consecutive_error_count >= 5:
            self.active = False
            # TODO: send notification when a source is deactivated

        super().save(*args, **kwargs)

    def fetch(self):
        """
        Fetches the RSS feed from the source URL, parses it with feedparser,
        and creates or updates RssItem records with their embeddings.
        """

        try:
            response = requests.get(self.url, headers={
                'User-Agent': 'Mozilla/5.0'
            }, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            # Log the error
            self.consecutive_error_count += 1
            self.last_fetch_error = f"Request error: {str(e)}"
            self.save()
            return

        feed = feedparser.parse(response.content)

        # Check if parsing had errors
        if feed.bozo:
            self.consecutive_error_count += 1
            self.last_fetch_error = f"Feed parsing error: {feed.bozo_exception}"
            self.save()
            return

        for entry in feed.entries:
            # Ensure there is a link to identify the item
            link = entry.get('link')
            if not link:
                continue

            # Remove query string parameters and fragments from the link
            parsed_url = urlparse(link)
            clean_link = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

            # Parse the published date if available
            published = None
            if 'published_parsed' in entry and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])

            # Create a new item or get the existing one based on the unique link
            item, created = RssItem.objects.get_or_create(
                link=clean_link,
                defaults={
                    'source': self,
                    'title': entry.get('title', ''),
                    'description': entry.get('description', ''),
                    'published_date': published,
                }
            )

            # Optionally update the item if fields have changed
            if not created:
                updated = False
                new_title = entry.get('title', '')
                new_description = entry.get('description', '')
                if item.title != new_title:
                    item.title = new_title
                    updated = True
                if item.description != new_description:
                    item.description = new_description
                    updated = True
                if published and item.published_date != published:
                    item.published_date = published
                    updated = True
                if updated:
                    item.save()

            # Generate the embedding if it isn't set already
            if item.embedding is None:
                item.update_embedding()

        self.last_fetch_error = None
        self.save()


class RssItem(models.Model):
    """Tracks per-entry ingestion state for a feed (dedupe, audit, linking)."""

    feed = models.ForeignKey(RssFeed, related_name='items', on_delete=models.CASCADE)
    guid = models.CharField(max_length=500)
    link = models.URLField(unique=True, max_length=500)

    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Status(models.TextChoices):
        NEW = "new", "New"
        UPSERTED = "upserted", "Upserted"
        SKIPPED = "skipped", "Skipped"
        ERROR = "error", "Error"

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    error_message = models.TextField(blank=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    # Reference the content object, if the RSS item is fetched
    content = models.ForeignKey('contents.Content', blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            HnswIndex(
                name='rssitem_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def __str__(self):
        return self.title

    def update_embedding(self):
        """
        Combines the title and description of the item and uses OpenAI's
        Embedding API to compute the embedding vector.
        """
        with OpenAI() as client:
            # Prepare the text to be embedded
            embed_text = f"{self.title}\n{self.description or ''}"
            response = client.embeddings.create(
                input=embed_text,
                model='text-embedding-3-small'
            )
        self.embedding = response.data[0].embedding
        self.save()

    def get_rssitem_summary(self):
        return f'{self.title}\n\n{strip_tags(self.description)}\n'

    @property
    def source_name(self) -> str:
        """
        Human-readable bucket label for diversification.
        Falls back to the feed’s domain if .name is blank.
        """
        src = self.source  # FK → RssSource
        return src.name or str(src)  # __str__ already gives the domain

