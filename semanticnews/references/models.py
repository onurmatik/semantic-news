import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import models
from django.utils import timezone


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    # ``fromisoformat`` cannot parse ``Z`` as UTC, so replace it.
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


@dataclass
class ReferenceMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None
    content_excerpt: Optional[str] = None
    status_code: Optional[int] = None
    raw_payload: Optional[dict] = None


class Reference(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    url = models.URLField(max_length=500)
    normalized_url = models.URLField(max_length=500, unique=True)
    domain = models.CharField(max_length=200, db_index=True, blank=True)

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    fetch_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    status_code = models.PositiveIntegerField(null=True, blank=True)

    meta_title = models.CharField(max_length=500, blank=True)
    meta_description = models.TextField(blank=True)
    meta_published_at = models.DateTimeField(null=True, blank=True)
    lead_image_url = models.URLField(max_length=500, blank=True)
    content_excerpt = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    content_version = models.PositiveIntegerField(default=1)
    fetch_error = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    topics = models.ManyToManyField(
        "topics.Topic",
        through="TopicReference",
        related_name="references",
        blank=True,
    )

    class Meta:
        ordering = ("-last_fetched_at", "-first_seen_at")

    def __str__(self):
        return self.meta_title or self.url

    @staticmethod
    def normalize_url(url: str) -> str:
        if not url:
            raise ValueError("URL is required")

        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        if not netloc and parsed.path:
            # Handle URLs without explicit scheme like example.com
            parsed = urlparse(f"{scheme}://{parsed.path}")
            netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = parsed.path or "/"
        if not path.startswith("/"):
            path = f"/{path}"

        normalized = urlunparse(
            (scheme, netloc, path.rstrip("/") or "/", "", parsed.query, "")
        )
        return normalized

    @staticmethod
    def extract_metadata(html: str, status_code: Optional[int] = None) -> ReferenceMetadata:
        if not html:
            payload = {"status_code": status_code} if status_code is not None else {}
            return ReferenceMetadata(status_code=status_code, raw_payload=payload)

        soup = BeautifulSoup(html, "html.parser")

        def _first_meta(*names: str) -> Optional[str]:
            for name in names:
                tag = soup.find("meta", attrs={"property": name}) or soup.find(
                    "meta", attrs={"name": name}
                )
                if tag and tag.get("content"):
                    return tag.get("content").strip()
            return None

        og_title = _first_meta("og:title")
        og_description = _first_meta("og:description")
        og_image = _first_meta("og:image") or _first_meta("twitter:image")
        og_published_at = _first_meta("article:published_time", "og:published_time")

        title_tag = soup.find("title")
        title_text = title_tag.text.strip() if title_tag and title_tag.text else None

        meta_description = _first_meta("description")

        body_text = soup.get_text(" ", strip=True) if soup else ""
        content_excerpt = body_text[:800]

        payload = {"status_code": status_code}

        return ReferenceMetadata(
            title=og_title or title_text,
            description=og_description or meta_description,
            published_at=_parse_iso_datetime(og_published_at),
            image_url=og_image,
            content_excerpt=content_excerpt,
            status_code=status_code,
            raw_payload=payload,
        )

    def _update_hash_and_version(self, new_excerpt: str) -> None:
        new_hash = ""
        if new_excerpt:
            new_hash = hashlib.sha256(
                new_excerpt.encode("utf-8", errors="ignore")
            ).hexdigest()

        if new_hash and self.content_hash and new_hash != self.content_hash:
            self.content_version = (self.content_version or 1) + 1
        elif not self.content_hash and new_hash:
            self.content_version = self.content_version or 1
        self.content_hash = new_hash

    def should_refresh(self) -> bool:
        if self.fetch_status == self.STATUS_PENDING:
            return True
        if self.last_fetched_at is None:
            return True
        return self.last_fetched_at < timezone.now() - timedelta(hours=6)

    def refresh_metadata(self, *, timeout: int = 8, commit: bool = True) -> ReferenceMetadata:
        headers = {
            "User-Agent": "SemanticNews/1.0 (+https://example.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        metadata = ReferenceMetadata()
        try:
            response = requests.get(
                self.url,
                timeout=timeout,
                headers=headers,
                allow_redirects=True,
            )
            metadata = self.extract_metadata(response.text, response.status_code)
            self.fetch_status = self.STATUS_SUCCEEDED
            self.fetch_error = ""
        except Exception as exc:
            self.fetch_status = self.STATUS_FAILED
            self.fetch_error = str(exc)
            metadata = ReferenceMetadata(status_code=None, raw_payload={})

        self.status_code = metadata.status_code
        self.last_fetched_at = timezone.now()

        if metadata.title:
            self.meta_title = metadata.title[:500]
        if metadata.description:
            self.meta_description = metadata.description
        self.meta_published_at = metadata.published_at
        self.lead_image_url = metadata.image_url[:500] if metadata.image_url else ""
        self.content_excerpt = metadata.content_excerpt or ""

        self.raw_payload = metadata.raw_payload or {}
        self._update_hash_and_version(self.content_excerpt)

        if commit:
            self.save()

        return metadata

    def save(self, *args, **kwargs):
        if self.url:
            self.normalized_url = self.normalize_url(self.url)
        if not self.domain and self.normalized_url:
            parsed = urlparse(self.normalized_url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            self.domain = domain
        super().save(*args, **kwargs)


class TopicReference(models.Model):
    reference = models.ForeignKey(
        Reference, related_name="topic_links", on_delete=models.CASCADE
    )
    topic = models.ForeignKey(
        "topics.Topic", related_name="topic_reference_links", on_delete=models.CASCADE
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    added_at = models.DateTimeField(auto_now_add=True)
    is_suggested = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    summary = models.TextField(blank=True)
    key_facts = models.JSONField(default=list, blank=True)
    content_version_snapshot = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("reference", "topic")
        ordering = ("-added_at",)

    def __str__(self):
        return f"{self.reference} → {self.topic}"
