# contents/services.py
from __future__ import annotations
from typing import Optional
from urllib.parse import urlparse
from django.db import transaction
from sources.models import Site, Content
from .registry import NormalizedContent

def _get_or_create_site_by_domain(domain: str) -> Optional[Site]:
    if not domain:
        return None
    domain = domain.lower()
    site, _ = Site.objects.get_or_create(domain=domain, defaults={"name": domain})
    return site

@transaction.atomic
def upsert_normalized(nc: NormalizedContent) -> Content:
    """
    Insert/update a Content row from normalized data.
    - URL is optional (uploads/snippets). If URL present, we dedupe on (url, content_type).
    """
    site = None
    if nc.site_domain:
        site = _get_or_create_site_by_domain(nc.site_domain)
    elif nc.url:
        site = _get_or_create_site_by_domain(urlparse(nc.url).netloc)

    qs = Content.objects
    obj = None

    if nc.url:
        obj = qs.filter(url=nc.url, content_type=nc.content_type).first()

    if obj:
        # Update a few mutable fields
        obj.title = nc.title or obj.title
        obj.summary = nc.summary or obj.summary
        obj.markdown = nc.markdown or obj.markdown
        obj.language_code = nc.language_code or obj.language_code
        obj.published_at = nc.published_at or obj.published_at
        obj.metadata = {**(obj.metadata or {}), **(nc.metadata or {})} if nc.metadata else obj.metadata
        if site and not obj.site:
            obj.site = site
        obj.save(update_fields=[
            "title", "summary", "markdown", "language_code", "published_at", "metadata", "site"
        ])
        return obj

    # Create new
    obj = Content.objects.create(
        site=site,
        url=nc.url,
        content_type=nc.content_type,
        title=nc.title,
        summary=nc.summary if hasattr(nc, "summary") else None,
        markdown=nc.markdown,
        published_at=nc.published_at,
        language_code=nc.language_code or "",
        metadata=nc.metadata or {},
    )
    return obj
