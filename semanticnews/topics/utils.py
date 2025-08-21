import hashlib
import hmac
from collections import OrderedDict
from datetime import timedelta
from operator import attrgetter
from typing import Any, Callable, Tuple, List, Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import QuerySet
from django.utils import timezone
from pgvector.django import L2Distance
from slugify import slugify

from ..topics.models import Keyword

User = get_user_model()


async def get_or_create_article_from_rssitem(rssitem_link: str, user_lazy):
    user_id = await sync_to_async(lambda: user_lazy.id)()
    user = await User.objects.aget(pk=user_id)

    try:
        rssitem = await RssItem.objects.select_related('fetched_article').aget(link=rssitem_link)
    except RssItem.DoesNotExist:
        raise ValueError(f"No RSS item found with link: {rssitem_link}")

    # If already fetched, return the existing article
    if rssitem.fetched_article:
        return rssitem.fetched_article

    # Get article with rssitem link
    article = await sync_to_async(lambda: Article.objects.filter(url=rssitem_link).first())()

    if not article:
        agent = FetchNewsFromRSSItemAgent()
        payload = await agent.run(
            f"# {rssitem.title}\n"
            f"{rssitem.published_date}\n"
            f"{rssitem.description}\n"
            f"{rssitem.link}\n"
        )

        article = Article(
            url=payload.url,
            title_original=payload.title,
            time=rssitem.published_date,
            lang=payload.lang,
            summary=payload.summary,
            keywords=payload.keywords,
            created_by=user,
        )
        await article.asave()

        # Create keywords from article.keywords
        for kw in article.keywords:
            await ensure_keyword(kw)

    rssitem.fetched_article = article
    await rssitem.asave()

    return article


async def ensure_keyword(name):
    slug = slugify(name)
    try:
        # Look up by slug, create if missing
        return await Keyword.objects.aget_or_create(
            slug=slug,
            defaults={'name': name}
        )
    except IntegrityError:
        keyword = await Keyword.objects.aget(slug=slug)
        return keyword, False


async def add_article_to_topic(topic, article_uuid: str, user):
    """
    Attach a single article (by UUID) to the given topic.
    Returns a tuple (created: bool, article: Article).
    """
    # fetch the Article instance
    article = await Article.objects.aget(uuid=article_uuid)

    # create the TopicArticle relation if it doesn't exist
    relation, created = await TopicArticle.objects.aget_or_create(
        topic=topic,
        article=article,
        defaults={'added_by': user}
    )

    return created, article


async def add_video_to_topic(topic, video_chunk_id: str, user):
    """
    Attach a single video_chunk (by id) to the given topic.
    Returns a tuple (created: bool, video_chunk: VideoTranscriptChunk).
    """
    # fetch the VideoTranscriptChunk instance
    video_chunk = await VideoTranscriptChunk.objects.aget(id=video_chunk_id)

    # fetch the related transcript
    transcript = await VideoTranscript.objects.aget(pk=video_chunk.transcript_id)

    # fetch the Video record
    video = await Video.objects.aget(pk=transcript.video_id)

    # create the TopicVideo relation if it doesn't exist
    relation, created = await TopicVideo.objects.aget_or_create(
        topic=topic,
        video=video,
        video_chunk=video_chunk,
        defaults={
            'added_by': user,
            'processed': True,
        },
    )

    return created, video_chunk


def get_recommended_articles(topics, limit=5):
    # Keep only those with embeddings
    emb_topics = [t for t in list(topics) if t.embedding is not None]
    if not emb_topics:
        return Article.objects.none()

    # Compute the centroid
    centroid = [
        sum(dim_vals) / len(emb_topics)
        for dim_vals in zip(*[list(t.embedding) for t in emb_topics])
    ]

    return (
        Article.objects
               .filter(
                   embedding__isnull=False,
                   topicarticle__topic__in=topics,
               )
               .annotate(
                   distance=L2Distance('embedding', centroid)
               )
               .order_by('distance')
               .distinct()[:limit]
    )


def diversify_by_source(qs: QuerySet, *, limit: int = 3, buffer_size: int | None = None,
                        source_getter: Callable[[Any], str] = lambda obj: getattr(obj, "source", None)) -> List[Any]:
    """
    Return **≤ limit** rows, with **max one per distinct source**.

    One SQL query is issued: the slice ``qs[:buffer_size]`` becomes ``LIMIT``.
    The buffer defaults to ``min(limit * 10, 100)`` so never pull thousands of rows by mistake.
    """
    buffer_size = min(buffer_size or limit * 10, 100)
    candidates = qs[:buffer_size]  # single LIMIT query
    chosen = OrderedDict()  # preserves first-seen order

    for obj in candidates:
        src = source_getter(obj)
        if src not in chosen:
            chosen[src] = obj
            if len(chosen) == limit:
                break

    return list(chosen.values())


def build_recommendations(
        *,
        embedding: Optional[Any],  # None ⇢ time-based | Vector ⇢ distance-based
        since_days: int = 2,
        limit: int = 3,
):
    """
    1.  Build candidate `QuerySet`s for Article / RssItem / VideoTranscriptChunk
        according to *embedding* or *recency*.
    2.  Pass each through `diversify_by_source`.
    3.  Return three plain Python **lists** pre-prefetched for template consumption.
    """
    if embedding is not None:
        # distance-based candidates
        rec_articles = (Article.objects
                        .filter(embedding__isnull=False)
                        .annotate(distance=L2Distance('embedding', embedding))
                        .order_by('distance'))
        rec_rss_items = (RssItem.objects
                         .filter(fetched_article__isnull=True,
                                 embedding__isnull=False)
                         .annotate(distance=L2Distance('embedding', embedding))
                         .order_by('distance'))
        rec_videos = (VideoTranscriptChunk.objects
                      .filter(embedding__isnull=False)
                      .annotate(distance=L2Distance('embedding', embedding))
                      .order_by('distance'))
    else:
        # recency-based candidates
        since = timezone.now() - timedelta(days=since_days)
        rec_articles = (Article.objects
                        .filter(time__gte=since)
                        .order_by('-time'))
        rec_rss_items = (RssItem.objects
                         .filter(fetched_article__isnull=True,
                                 published_date__gte=since)
                         .order_by('-published_date'))
        rec_videos = (VideoTranscriptChunk.objects
                      .filter(transcript__video__published_at__gte=since)
                      .order_by('-transcript__video__published_at'))

    # diversify
    articles = diversify_by_source(
        rec_articles.prefetch_related('topic_set'),
        limit=limit,
        source_getter=attrgetter('source'),
    )
    rss_items = diversify_by_source(
        rec_rss_items.select_related('source'),
        limit=limit,
        source_getter=attrgetter('source_name'),
    )
    videos = diversify_by_source(
        rec_videos.prefetch_related('topic_set', 'transcript__video__channel'),
        limit=limit,
        source_getter=attrgetter('source_name'),
    )
    return articles, rss_items, videos


def make_suggestion_token(suggestion: str) -> str:
    """
    Create an HMAC-SHA256 of the suggestion text using SECRET_KEY.
    The client will send this back to prove the response really came from the agent.
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        suggestion.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def valid_suggestion_token(suggestion: str, token: str) -> bool:
    """
    Constant-time compare so clients can’t forge tokens.
    """
    expected = make_suggestion_token(suggestion)
    return hmac.compare_digest(expected, token)