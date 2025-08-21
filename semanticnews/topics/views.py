import calendar
import json

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate, ExtractMonth, ExtractDay
from django.urls import reverse
from django.utils import timezone as django_timezone, formats
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.db.models import Q, Count, ExpressionWrapper, F, Func, Value, DurationField, FloatField
from googleapiclient.discovery import build
from pgvector.django import L2Distance
from slugify import slugify

from .agents import TopicListSuggestionAgent, TopicEvaluationAgent, TopicCreationAgent, TopicSuggestionAgent
from .models import Topic, Keyword, TopicContent
from .utils import add_article_to_topic, get_or_create_article_from_rssitem, add_video_to_topic, ensure_keyword, \
    build_recommendations, valid_suggestion_token, make_suggestion_token


def topics_list(request, keyword):
    if keyword.embedding is None:
        keyword.save()  # creates the embedding

    half_life_days = 30
    half_life_sec = half_life_days * 24 * 3600

    now = django_timezone.now()

    topics_qs = (
        Topic.objects
        .filter(status='p')
        # raw L2 distance
        .annotate(dist=L2Distance('embedding', keyword.embedding))
        # age = now - created_at    -> interval
        .annotate(age=ExpressionWrapper(
            Value(now) - F('created_at'),
            output_field=DurationField()
        ))
        # convert interval to seconds: EXTRACT(EPOCH FROM age)
        .annotate(age_sec=Func(
            F('age'),
            function='EXTRACT',
            template="EXTRACT(EPOCH FROM %(expressions)s)"
        ))
        # decay = exp(age_sec / half_life_sec)
        .annotate(decay=Func(
            F('age_sec') / Value(float(half_life_sec)),
            function='EXP',
            output_field=FloatField()
        ))
        # final score
        .annotate(score=F('dist') * F('decay'))
        .order_by('score')  # smaller score = closer & newer
    )

    content_qs = (
        TopicContent.objects
        # raw L2 distance
        .annotate(dist=L2Distance('embedding', keyword.embedding))
        # age = now - added_at    -> interval
        .annotate(age=ExpressionWrapper(
            Value(now) - F('added_at'),
            output_field=DurationField()
        ))
        # convert interval to seconds: EXTRACT(EPOCH FROM age)
        .annotate(age_sec=Func(
            F('age'),
            function='EXTRACT',
            template="EXTRACT(EPOCH FROM %(expressions)s)"
        ))
        # decay = exp(age_sec / half_life_sec)
        .annotate(decay=Func(
            F('age_sec') / Value(float(half_life_sec)),
            function='EXP',
            output_field=FloatField()
        ))
        # final score
        .annotate(score=F('dist') * F('decay'))
        .order_by('score')  # smaller score = closer & newer
    )

    rec_articles, rec_rss_items, rec_videos = build_recommendations(
        embedding=keyword.embedding,
        limit=3,
    )

    return render(request, 'topics/topics_keyword_list.html', {
        'keyword': keyword,
        'topics': topics_qs[:20],
        'related_content': content_qs[:3],
        'recommended_articles': rec_articles,
        'recommended_rss_items': rec_rss_items,
        'recommended_videos': rec_videos,
    })


def topics_detail(request, slug):
    try:
        topic = Topic.objects.get(slug=slug)
    except Topic.DoesNotExist:
        keyword = get_object_or_404(Keyword, slug=slug)
        return topics_list(request, keyword=keyword)

    return render(request, 'topics/topics_detail.html', {
        'topic': topic,
    })


# Topic Creation

@login_required
async def get_topic_suggestions(request):
    if request.method != "POST":
        return JsonResponse({"error": _("Invalid HTTP method")}, status=405)

    data = json.loads(request.body)
    search_query = data.get("search_query", "").strip()
    if not search_query:
        return JsonResponse({"error": _("Empty search query")}, status=400)

    agent = TopicListSuggestionAgent()
    response = await agent.run(search_query, lang='tr')

    return JsonResponse({"suggestions": response.topics})


@login_required
async def create_new_topic(request):
    data = json.loads(request.body)
    topic_name = data.get('topicName', '').strip()
    event_date_str = data.get('event_date')
    suggestion_token = data.get('suggestion_token')

    if not topic_name:
        return JsonResponse({"error": "Topic is required"}, status=400)

    # Handle suggestion-token flow (accepted revision):
    if suggestion_token:
        if not valid_suggestion_token(topic_name, suggestion_token):
            return JsonResponse({"error": "Invalid suggestion token"}, status=400)
        creation_agent = TopicCreationAgent()
        topic_schema = await creation_agent.run(topic_name)
    else:
        # First pass: Evaluate the topic
        evaluation_agent = TopicEvaluationAgent()
        evaluation = await evaluation_agent.run(topic_name)

        if evaluation.status == 'revision':
            suggested = evaluation.suggested_topic
            payload = {
                "reason": evaluation.reason,
                "suggested_topic": suggested,
            }
            if suggested:  # Only generate token if we have a suggestion
                payload["suggestion_token"] = make_suggestion_token(suggested)

            return JsonResponse(payload, status=400)

        elif evaluation.status == "reject":
            # Handle reject explicitly:
            return JsonResponse({
                "error": evaluation.reason or "Topic rejected"
            }, status=400)

        # If "OK", parse details with TopicCreationAgent
        creation_agent = TopicCreationAgent()
        topic_schema = await creation_agent.run(topic_name)

    # Unpack the structured topic data
    parsed_name = topic_schema.name.strip()
    raw_event_date = event_date_str or topic_schema.event_date
    try:
        event_date = datetime.strptime(raw_event_date, "%Y-%m-%d").date() if raw_event_date else None
    except ValueError:
        event_date = None
    categories = topic_schema.categories
    significance = topic_schema.significance

    # Check if the topic exists
    topic = await Topic.objects.filter(
        slug=slugify(parsed_name),
        created_by=request.user,
    ).afirst()

    if not topic:
        # Create a new topic
        topic = await Topic.objects.acreate(
            name=parsed_name,
            categories=categories,
            significance=significance[0],
            event_date=event_date,
            created_by=request.user,
        )
        for cat in categories:
            # Create keywords from categories
            await ensure_keyword(cat)

    return JsonResponse({
        'redirect_url': topic.get_absolute_url(),
        'uuid': str(topic.uuid),
    })


@login_required
def topic_translation_status(request, topic_uuid):
    """
    Return {"translated": bool, "name_en": "…"} for the given topic UUID.
    """
    try:
        topic = Topic.objects.only("name_en").get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({"error": "Topic not found"}, status=404)

    return JsonResponse(
        {"translated": bool(topic.name_en), "name_en": topic.name_en}
    )


# Deletion

@login_required
@require_http_methods(["POST"])
def delete_topic(request, slug):
    topic = Topic.objects.filter(
        slug=slug,
        created_by=request.user,
        status='d'
    ).first()

    if not topic:
        return JsonResponse(
            {'error': 'Draft topic not found or not owned by you.'},
            status=404
        )

    topic.delete()

    return JsonResponse({
        'redirect_url': reverse('home'),
        'uuid': str(topic.uuid),
        'message': _('Draft deleted successfully.'),
    })


# Adding content to topics

@login_required
def get_content_suggestions(request, topic_uuid):
    suggestions_count = 10
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({'error': _('Topic not found.')}, status=404)

    # RSS: Exclude if rss item has fetched_article
    related_rssitems = RssItem.objects.filter(embedding__isnull=False) \
                           .exclude(fetched_article__isnull=False) \
                           .order_by(L2Distance('embedding', topic.embedding))[:suggestions_count]

    rss_data = []
    for rssitem in related_rssitems:
        if rssitem.published_date:
            day = rssitem.published_date.strftime('%d')
            month = _(rssitem.published_date.strftime('%B'))
            year = rssitem.published_date.strftime('%Y')
            formatted_date = f"{day} {month} {year}"
        else:
            formatted_date = ''
        rss_data.append({
            'title': rssitem.title,
            'link': rssitem.link,
            'description': strip_tags(rssitem.description) if rssitem.description else '',
            'date': formatted_date,
            'source': str(rssitem.source) if rssitem.source else '',
        })

    # Exclude already-related articles
    related_article_uuids = TopicArticle.objects.filter(topic=topic).values_list('article__uuid', flat=True)

    # Articles
    related_articles = Article.objects.filter(embedding__isnull=False) \
                           .exclude(uuid__in=related_article_uuids) \
                           .order_by(L2Distance('embedding', topic.embedding))[:suggestions_count]

    article_data = []
    for article in related_articles:
        if article.time:
            article_date = article.time.date()
            day = article_date.strftime('%d')
            month = _(article_date.strftime('%B'))
            year = article_date.strftime('%Y')
            formatted_date = f"{day} {month} {year}"
        else:
            formatted_date = ''
        article_data.append({
            'title': article.get_title_i18n(),
            'link': article.url,
            'description': article.get_summary_i18n(),
            'date': formatted_date,
            'source': str(article.source) if article.source else '',
            'uuid': str(article.uuid),
        })

    # Exclude already-related videos
    related_chunk_ids = TopicVideo.objects.filter(topic=topic).values_list('video_chunk_id', flat=True)

    # Relevant YouTube videos; only one chunk per video (the one with the lowest distance)
    all_chunks = (
        VideoTranscriptChunk.objects
            .filter(embedding__isnull=False)
            .annotate(dist=L2Distance("embedding", topic.embedding))
            .exclude(pk__in=related_chunk_ids)
            .order_by("dist")[:100] # grab a reasonable buffer for deduplication
    )

    # pick the first chunk for each video
    seen_videos = set()
    related_chunks = []
    for chunk in all_chunks:
        vid = chunk.transcript.video_id
        if vid in seen_videos:
            continue
        related_chunks.append(chunk)
        seen_videos.add(vid)
        if len(related_chunks) >= (suggestions_count - 5):
            break

    video_data = []
    for chunk in related_chunks:
        video_date = chunk.transcript.video.published_at.date()
        day = video_date.strftime('%d')
        month = _(video_date.strftime('%B'))
        year = video_date.strftime('%Y')
        formatted_date = f"{day} {month} {year}"
        video = chunk.transcript.video
        video_data.append({
            'title': video.title,
            'link': chunk.get_video_url(),
            'embed_url': chunk.get_embed_url(),
            'description': chunk.revised_text,
            'date': formatted_date,
            'channel': str(video.channel) if video.channel else '',
            'id': chunk.id,
        })

    return JsonResponse({
        'rss_data': rss_data,
        'article_data': article_data,
        'video_data': video_data,
    })


@login_required
@require_http_methods(["POST"])
async def add_article(request, topic_uuid, threshold=0.5):
    try:
        topic = await Topic.objects.aget(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({'error': _('Topic not found.')}, status=404)

    data = json.loads(request.body)
    article_uuid = data.get('article')
    rssitem_link = data.get('rssitem')

    if not article_uuid and not rssitem_link:
        return JsonResponse({'error': _('No content selected.')}, status=400)

    # Fetch or create the Article instance
    if rssitem_link:
        try:
            article = await get_or_create_article_from_rssitem(rssitem_link, request.user)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        try:
            article = await Article.objects.aget(uuid=article_uuid)
        except Article.DoesNotExist:
            return JsonResponse({'error': _('Article not found.')}, status=404)

    relevance = get_relevance(article.embedding, topic.embedding)
    if not relevance or relevance < threshold:
        return JsonResponse({
            'error': _('Relevance is too low.')
        })

    # Add the article to the topic
    created, article = await add_article_to_topic(topic, str(article.uuid), request.user)

    if created:
        message = article.get_title_i18n()
    else:
        message = _('Article “%(title)s” was already added.') % {'title': article.get_title_i18n()}

    return JsonResponse({
        'message': message,
        'redirect_url': topic.get_absolute_url(),
    })


@login_required
@require_http_methods(["POST"])
async def add_user_article(request, topic_uuid, threshold=0.5):
    try:
        topic = await Topic.objects.aget(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({'error': _('Topic not found.')}, status=404)

    data = json.loads(request.body)
    content_url = data.get('content_url')

    if not content_url:
        return JsonResponse({'error': _('No URL given.')}, status=400)

    article = await Article.objects.filter(url=content_url).afirst()

    if not article:
        agent = FetchUserNewsAgent()
        payload = await agent.run(content_url)

        article = await Article.objects.acreate(
            url=payload.url,
            title_original=payload.title,
            time=payload.date,
            lang=payload.lang,
            summary=payload.summary,
            keywords=payload.keywords,
            created_by=request.user,
        )

        # Create keywords from article.keywords
        for kw in article.keywords:
            await ensure_keyword(kw)

    relevance = get_relevance(article.embedding, topic.embedding)
    if not relevance or relevance < threshold:
        return JsonResponse({
            'error': _('Relevance is too low.')
        })

    # Add the article to the topic
    created, article = await add_article_to_topic(topic, str(article.uuid), request.user)

    if created:
        message = article.get_title_i18n()
    else:
        message = _('Article “%(title)s” was already added.') % {'title': article.get_title_i18n()}

    return JsonResponse({
        'message': message,
        'redirect_url': topic.get_absolute_url(),
    })


@login_required
@require_http_methods(["POST"])
async def add_video(request, topic_uuid, threshold=0.5):
    try:
        topic = await Topic.objects.aget(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({'error': _('Topic not found.')}, status=404)

    data = json.loads(request.body)
    chunk_id = data.get('chunk_id')
    if not chunk_id:
        return JsonResponse({'error': _('No chunk_id provided')}, status=400)

    video_chunk = await VideoTranscriptChunk.objects.filter(id=chunk_id).afirst()
    if not video_chunk:
        return JsonResponse({'error': _('Video not found.')}, status=404)

    relevance = get_relevance(video_chunk.embedding, topic.embedding)
    if not relevance or relevance < threshold:
        return JsonResponse({
            'error': _('Relevance is too low.')
        })

    # Add the video_chunk to the topic
    created, video_chunk = await add_video_to_topic(topic, str(video_chunk.id), request.user)

    transcript = await VideoTranscript.objects.aget(pk=video_chunk.transcript_id)
    video = await Video.objects.aget(pk=transcript.video_id)
    video_title = video.title

    if created:
        message = video_title
    else:
        message = _('Video “%(title)s” was already added.') % {'title': video_title}

    return JsonResponse({
        'message': message,
        'redirect_url': topic.get_absolute_url(),
    })


@login_required
@require_http_methods(["POST"])
async def add_user_video(request, topic_uuid):
    try:
        topic = await Topic.objects.aget(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return JsonResponse({'error': _('Topic not found.')}, status=404)

    data = json.loads(request.body)
    url = (data.get('content_url') or '').strip()
    if not url:
        return JsonResponse({'error': _('No URL given.')}, status=400)

    try:
        video_id, video_type = extract_video_id_and_type(url)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    # Check transcript availability before creating video
    try:
        list_youtube_transcripts(video_id)
    except Exception as exc:
        _, warning = map_transcript_exception(exc)
        return JsonResponse({'transcript_error': warning}, status=400)

    # Check for existing Video
    video = await Video.objects.filter(video_id=video_id).afirst()
    if not video:
        try:
            meta = fetch_youtube_metadata(video_id)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

        # Get or create Channel
        channel, channel_created = await Channel.objects.aget_or_create(
            channel_id=meta["channel_id"],
            defaults={
                'handle': meta["channel_title"],
                'title': meta["channel_title"],
                'created_by': request.user,
                'active': False,
            }
        )

        # Create Video record
        video = await Video.objects.acreate(
            channel=channel,
            video_id=video_id,
            title=meta["title"],
            description=meta["description"],
            thumbnail=meta["thumbnail"],
            published_at=meta["published_at"],
            is_short=True if video_type == "shorts" else False,
        )

    relation, created = await TopicVideo.objects.aget_or_create(
        topic=topic,
        video=video,
        defaults={'added_by': request.user}
    )

    if created:
        message = video.title
    else:
        message = _('Video “%(title)s” was already added.') % {'title': video.title}

    return JsonResponse({
        "message": message,
        "redirect_url": topic.get_absolute_url(),
    })


def extract_video_id_and_type(url: str) -> tuple[str, str]:
    """
    Extract the 11-char YouTube ID from various URL forms:
      - https://youtu.be/<ID>
      - https://www.youtube.com/watch?v=<ID>
      - https://www.youtube.com/embed/<ID>
      - https://www.youtube.com/live/<ID>
      - https://www.youtube.com/shorts/<ID>
      Return (video_id, type)
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lstrip('/')  # e.g. "watch", "embed/XYZ", "live/ABC", "shorts/DEF"

    video_type = None
    video_id = None

    if 'youtu.be' in host:
        video_id = path.split('/')[0]

    elif 'youtube.com' in host:
        # 1) watch?v=<ID>
        qs = parse_qs(parsed.query)
        if 'v' in qs and qs['v']:
            video_id = qs['v'][0]
        else:
            # 2) embed/<ID>, live/<ID>, shorts/<ID>
            parts = path.split('/')
            if parts and parts[0] in ('embed', 'live', 'shorts') and len(parts) > 1:
                video_id = parts[1]
                video_type = parts[0]

    if not video_id:
        raise ValueError(f"Could not extract YouTube ID from {url!r}")

    return video_id, video_type


def fetch_youtube_metadata(video_id: str) -> dict:
    youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
    resp = (
        youtube.videos()
               .list(part="snippet", id=video_id)
               .execute()
    )
    items = resp.get("items") or []
    if not items:
        raise ValueError("Video not found on YouTube")
    snippet = items[0]["snippet"]
    return {
        "title":          snippet["title"],
        "description":    snippet["description"],
        "thumbnail":      snippet["thumbnails"]["medium"]["url"],
        "published_at":   datetime.strptime(
                              snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
                          ).replace(tzinfo=timezone.utc),
        "channel_id":     snippet["channelId"],
        "channel_title":  snippet["channelTitle"],
    }


# Content -> Topic

@login_required
@require_http_methods(["POST"])
async def get_content_topic_suggestion(request):
    data = json.loads(request.body)
    article_uuid = data.get('article')
    rssitem_link = data.get('rssitem')
    chunk_id = data.get('video')

    if not article_uuid and not rssitem_link and not chunk_id:
        return JsonResponse({'error': _('No content selected.')}, status=400)

    # Prepare containers and summary
    article_data, rssitem_data, video_data = [], [], []
    summary_text = ""

    if article_uuid:
        # Handle Article
        try:
            article = await Article.objects.aget(uuid=article_uuid)
        except Article.DoesNotExist:
            return JsonResponse({'error': _('Article not found.')}, status=404)

        # Prepare summary
        summary_text = article.get_article_summary()

        # Format date
        if article.time:
            article_date = article.time.date()
            day = article_date.strftime('%d')
            month = _(article_date.strftime('%B'))
            year = article_date.strftime('%Y')
            formatted_date = f"{day} {month} {year}"
        else:
            formatted_date = ''
        article_data.append({
            'title': article.get_title_i18n(),
            'link': article.url,
            'description': article.get_summary_i18n(),
            'date': formatted_date,
            'source': str(article.source) if article.source else '',
            'uuid': str(article.uuid),
        })

    elif rssitem_link:
        # Handle RSSItem
        try:
            rssitem = await RssItem.objects.select_related('source').aget(link=rssitem_link)
        except RssItem.DoesNotExist:
            return JsonResponse({'error': _('RSS not found.')}, status=404)

        # Prepare summary
        summary_text = rssitem.get_rssitem_summary()

        if rssitem.published_date:
            day = rssitem.published_date.strftime('%d')
            month = _(rssitem.published_date.strftime('%B'))
            year = rssitem.published_date.strftime('%Y')
            formatted_date = f"{day} {month} {year}"
        else:
            formatted_date = ''
        rssitem_data.append({
            'title': rssitem.title,
            'link': rssitem.link,
            'description': strip_tags(rssitem.description) if rssitem.description else '',
            'date': formatted_date,
            'source': str(rssitem.source) if rssitem.source else '',
        })

    elif chunk_id:
        # Handle Video Transcript Chunk
        try:
            chunk = await VideoTranscriptChunk.objects\
                .select_related('transcript__video__channel')\
                .aget(pk=chunk_id)
        except VideoTranscriptChunk.DoesNotExist:
            return JsonResponse({'error': _('Video not found.')}, status=404)

        video = chunk.transcript.video

        # Prepare summary
        summary_text = f"{video.title}\n\n{chunk.revised_text}\n"

        if video.published_at.date():
            video_date = video.published_at.date()
            day = video_date.strftime('%d')
            month = _(video_date.strftime('%B'))
            year = video_date.strftime('%Y')
            formatted_date = f"{day} {month} {year}"
        else:
            formatted_date = ''
        video_data.append({
            'title': video.title,
            'link': chunk.get_video_url(),
            'embed_url': chunk.get_embed_url(),
            'description': chunk.revised_text,
            'date': formatted_date,
            'channel': str(video.channel) if video.channel else '',
            'id': chunk.id,
        })

    # Generate topic suggestion based on summary_text
    agent = TopicSuggestionAgent()
    response = await agent.run(summary_text, lang='tr')

    return JsonResponse({
        'article': article_data,
        'rssitem': rssitem_data,
        'video': video_data,
        'topic_suggestion': response.topic,
    })


@login_required
@require_http_methods(["POST"])
def get_content_related_topics(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    article_uuid = payload.get("article")
    rssitem_link = payload.get("rssitem")
    chunk_id = payload.get("video")

    if not any([article_uuid, rssitem_link, chunk_id]):
        return JsonResponse({"error": "No content selected."}, status=400)

    embedding       = None
    exclude_topic_ids = []

    # ── Article branch ──
    if article_uuid:
        try:
            article = Article.objects.get(uuid=article_uuid)
        except Article.DoesNotExist:
            return JsonResponse({"error": "Article not found."}, status=404)
        embedding = article.embedding
        exclude_topic_ids = TopicArticle.objects.filter(
            article=article
        ).values_list("topic_id", flat=True)

    # ── RSSItem branch ──
    elif rssitem_link:
        try:
            rssitem = RssItem.objects.get(link=rssitem_link)
        except RssItem.DoesNotExist:
            return JsonResponse({'error': _('RSS not found.')}, status=404)

        embedding = rssitem.embedding

    # ── Video branch ──
    elif chunk_id:
        try:
            chunk = VideoTranscriptChunk.objects.get(pk=chunk_id)
        except VideoTranscriptChunk.DoesNotExist:
            return JsonResponse({"error": "Video not found."}, status=404)

        embedding = chunk.embedding
        exclude_topic_ids = TopicVideo.objects.filter(
            video_chunk=chunk
        ).values_list("topic_id", flat=True)

    related_topics = []
    if embedding is not None:
        qs = (
            Topic.objects
                 .exclude(embedding__isnull=True)
                 .exclude(name__isnull=True)
                 .exclude(id__in=exclude_topic_ids)
                 .exclude(status='r')
                 .order_by(L2Distance("embedding", embedding))
        )[:5]

        related_topics = list(qs.values("uuid", "name", "slug"))

    return JsonResponse({"related_topics": related_topics})
