from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from django.templatetags.static import static
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import gettext as _
from pgvector.django import L2Distance
import json

from django.db.models import Prefetch
from django.db.models.functions import Coalesce
from types import SimpleNamespace

from semanticnews.agenda.models import Event
from semanticnews.agenda.localities import (
    get_default_locality_label,
    get_locality_options,
)

from .models import (
    Topic,
    RelatedTopic,
    RelatedEntity,
    RelatedEvent,
    Source,
)
from semanticnews.widgets.data.models import TopicDataVisualization
from semanticnews.widgets.mcps.models import MCPServer


RELATED_ENTITIES_PREFETCH = Prefetch(
    "related_entities",
    queryset=RelatedEntity.objects.filter(is_deleted=False)
    .select_related("entity")
    .order_by("-created_at"),
    to_attr="prefetched_related_entities",
)


@login_required
def topic_create(request):
    """Create a draft topic and redirect to the inline editor."""

    topic = Topic.objects.create(created_by=request.user)
    return redirect(
        "topics_detail_edit",
        username=request.user.username,
        topic_uuid=topic.uuid,
    )


def _topic_is_visible_to_user(topic, user):
    """Return True if the topic should be visible to the given user."""

    if topic.status != "draft":
        return True

    if topic.created_by_id is None:
        return False

    return user.is_authenticated and user == topic.created_by


def _render_topic_detail(request, topic):
    if not _topic_is_visible_to_user(topic, request.user):
        raise Http404("Topic not found")

    context = _build_topic_page_context(topic, request.user, edit_mode=False)

    if topic.status != "published":
        context["is_unpublished"] = True

    context.update(_build_topic_metadata(request, topic, context))

    return render(request, "topics/topics_detail.html", context)


def topics_detail_redirect(request, topic_uuid, username):
    """Redirect topics accessed via UUID to their canonical slug URL."""

    topic = get_object_or_404(
        Topic.objects.select_related("created_by"),
        uuid=topic_uuid,
        created_by__username=username,
    )

    if not _topic_is_visible_to_user(topic, request.user):
        raise Http404("Topic not found")

    if not topic.slug:
        return _render_topic_detail(request, topic)

    return redirect("topics_detail", slug=topic.slug, username=username)


def topics_list(request):
    """Display the most recently updated published topics."""

    visualizations_prefetch = Prefetch(
        "data_visualizations",
        queryset=TopicDataVisualization.objects.order_by("-created_at"),
    )

    topics = (
        Topic.objects.filter(status="published")
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .select_related("created_by")
        .prefetch_related("recaps", "images", visualizations_prefetch)
        .order_by("-ordering_activity", "-created_at")
    )

    recent_events = (
        Event.objects.filter(status="published")
        .select_related("created_by")
        .prefetch_related("categories", "sources")
        .order_by("-date", "-created_at")[:5]
    )

    context = {
        "topics": topics,
        "recent_events": recent_events,
    }

    return render(request, "topics/topics_list.html", context)


def topics_detail(request, slug, username):
    queryset = Topic.objects.prefetch_related(
        "events",
        "recaps",
        "texts",
        "images",
        "documents",
        "webpages",
        "youtube_videos",
        "tweets",
        RELATED_ENTITIES_PREFETCH,
        "datas",
        "data_insights__sources",
        "data_visualizations__insight",
        Prefetch(
            "topic_related_topics",
            queryset=RelatedTopic.objects.select_related(
                "related_topic__created_by"
            ).order_by("-created_at"),
            to_attr="prefetched_related_topic_links",
        ),
    ).filter(
        titles__slug=slug,
        created_by__username=username,
    ).distinct()

    topic = get_object_or_404(queryset)

    return _render_topic_detail(request, topic)


def _build_topic_module_context(topic, user=None):
    """Collect related objects used to render topic content."""

    related_events = topic.active_events
    current_recap = topic.active_recaps.order_by("-created_at").first()
    latest_recap = (
        topic.active_recaps.filter(status="finished")
        .order_by("-created_at")
        .first()
    )
    related_entities = list(
        getattr(topic, "prefetched_related_entities", None)
        or topic.active_related_entities.select_related("entity").order_by("-created_at")
    )
    related_entities_payload = [
        {
            "name": relation.entity.name,
            "role": relation.role,
            "disambiguation": getattr(relation.entity, "disambiguation", None),
        }
        for relation in related_entities
        if relation.entity is not None
    ]
    related_entities_json = json.dumps(related_entities_payload, separators=(",", ":"))
    related_entities_json_pretty = json.dumps(related_entities_payload, indent=2)
    texts = list(topic.active_texts.order_by("display_order", "created_at"))
    documents = list(
        topic.active_documents.order_by("display_order", "-created_at")
    )
    webpages = list(
        topic.active_webpages.order_by("display_order", "-created_at")
    )
    datas = list(topic.active_datas.order_by("display_order", "created_at"))
    latest_data = max(datas, key=lambda item: item.created_at) if datas else None
    data_insights = list(
        topic.active_data_insights.prefetch_related("sources").order_by("-created_at")
    )
    data_visualizations = list(
        topic.active_data_visualizations
        .select_related("insight")
        .order_by("display_order", "created_at")
    )
    has_saved_data_content = bool(latest_data or data_insights or data_visualizations)
    youtube_videos = list(
        topic.active_youtube_videos.order_by("display_order", "-created_at")
    )
    youtube_video = youtube_videos[0] if youtube_videos else None
    tweets = list(
        topic.active_tweets.order_by("display_order", "-created_at")
    )

    related_topic_links = list(
        getattr(topic, "prefetched_related_topic_links", None)
        or RelatedTopic.objects.select_related("related_topic__created_by")
        .filter(topic=topic)
        .order_by("-created_at")
    )
    active_related_topic_links = [
        link for link in related_topic_links if not link.is_deleted
    ]
    is_authenticated = getattr(user, "is_authenticated", False)
    for link in active_related_topic_links:
        link.is_owned_by_topic_creator = (
            topic.created_by_id is not None
            and link.created_by_id == topic.created_by_id
        )
        link.is_owned_by_user = (
            bool(is_authenticated) and link.created_by_id == getattr(user, "id", None)
        )
    related_topics = [link.related_topic for link in active_related_topic_links]

    if topic.embedding is not None:
        suggested_events = (
            Event.objects.exclude(topics=topic)
            .exclude(embedding__isnull=True)
            .annotate(distance=L2Distance("embedding", topic.embedding))
            .order_by("distance")[:5]
        )
    else:
        suggested_events = Event.objects.none()

    return {
        "topic": topic,
        "related_events": related_events,
        "suggested_events": suggested_events,
        "current_recap": current_recap,
        "latest_recap": latest_recap,
        "related_entities": related_entities,
        "related_entities_json": related_entities_json,
        "related_entities_json_pretty": related_entities_json_pretty,
        "texts": texts,
        "latest_data": latest_data,
        "datas": datas,
        "data_insights": data_insights,
        "data_visualizations": data_visualizations,
        "data_button_status": "success" if has_saved_data_content else "finished",
        "youtube_video": youtube_video,
        "youtube_videos": youtube_videos,
        "tweets": tweets,
        "documents": documents,
        "webpages": webpages,
        "related_topic_links": active_related_topic_links,
        "related_topics": related_topics,
    }


def _resolve_data_widget_visibility(datas, data_insights):
    data_ids_with_insights = set()
    has_unsourced_insight = False

    for insight in data_insights:
        sources_manager = getattr(insight, "sources", None)
        if sources_manager is None:
            continue
        sources = list(sources_manager.all())
        if not sources:
            has_unsourced_insight = True
        for source in sources:
            source_id = getattr(source, "id", None)
            if source_id is not None:
                data_ids_with_insights.add(str(source_id))

    visibility = {}
    unsourced_assigned = False

    for data_obj in datas:
        identifier = getattr(data_obj, "id", None)
        if identifier is None:
            continue
        key = str(identifier)
        should_show = key in data_ids_with_insights
        if not should_show and has_unsourced_insight and not unsourced_assigned:
            should_show = True
            unsourced_assigned = True
        visibility[key] = should_show

    return visibility


def _build_primary_widgets(context, *, edit_mode=False):
    widgets = []
    texts = context.get("texts") or []
    datas = context.get("datas") or []
    data_visualizations = context.get("data_visualizations") or []
    documents = list(context.get("documents") or [])
    webpages = list(context.get("webpages") or [])
    tweets = list(context.get("tweets") or [])
    youtube_video = context.get("youtube_video")
    data_insights = context.get("data_insights") or []

    data_visibility = _resolve_data_widget_visibility(datas, data_insights)

    for text in texts:
        identifier = getattr(text, "id", None)
        if identifier is None:
            continue
        module_key = f"text:{identifier}"
        module = SimpleNamespace(module_key=module_key, text=text)
        widgets.append(
            SimpleNamespace(
                key=module_key,
                kind="text",
                display_order=getattr(text, "display_order", 0),
                module=module,
                edit_mode=edit_mode,
            )
        )

    for dataset in datas:
        identifier = getattr(dataset, "id", None)
        if identifier is None:
            continue
        key = str(identifier)
        widgets.append(
            SimpleNamespace(
                key=f"data:{key}",
                kind="data",
                display_order=getattr(dataset, "display_order", 0),
                data=dataset,
                show_data_insights=data_visibility.get(key, False),
                edit_mode=edit_mode,
            )
        )

    for visualization in data_visualizations:
        identifier = getattr(visualization, "id", None)
        if identifier is None:
            continue
        module_key = f"data_visualizations:{identifier}"
        module = SimpleNamespace(
            module_key=module_key,
            visualization=visualization,
        )
        widgets.append(
            SimpleNamespace(
                key=module_key,
                kind="data_visualization",
                display_order=getattr(visualization, "display_order", 0),
                module=module,
                edit_mode=edit_mode,
            )
        )

    embed_orders = []
    if youtube_video is not None:
        order = getattr(youtube_video, "display_order", None)
        if order is not None:
            embed_orders.append(order)
    for tweet in tweets:
        order = getattr(tweet, "display_order", None)
        if order is not None:
            embed_orders.append(order)
    if edit_mode or youtube_video or tweets:
        display_order = min(embed_orders) if embed_orders else 0
        widgets.append(
            SimpleNamespace(
                key="embeds",
                kind="embeds",
                display_order=display_order,
                youtube_video=youtube_video,
                tweets=tweets,
                edit_mode=edit_mode,
            )
        )

    reference_orders = []
    for document in documents:
        order = getattr(document, "display_order", None)
        if order is not None:
            reference_orders.append(order)
    for webpage in webpages:
        order = getattr(webpage, "display_order", None)
        if order is not None:
            reference_orders.append(order)

    if edit_mode or documents or webpages:
        display_order = min(reference_orders) if reference_orders else 0
        widgets.append(
            SimpleNamespace(
                key="references",
                kind="references",
                display_order=display_order,
                documents=documents,
                webpages=webpages,
                edit_mode=edit_mode,
            )
        )

    widgets.sort(key=lambda item: (item.display_order, item.key))
    return widgets


def _build_topic_page_context(topic, user=None, *, edit_mode=False):
    context = _build_topic_module_context(topic, user)
    context["primary_widgets"] = _build_primary_widgets(context, edit_mode=edit_mode)
    context["edit_mode"] = edit_mode
    return context


def _build_topic_metadata(request, topic, context):
    """Derive metadata required for SEO and social sharing."""

    default_description = _(
        "Stay informed with curated analysis from Semantic News."
    )
    context_topic = context.get("topic", topic)

    def _extract_recap_text():
        recap_candidates = []
        latest = context.get("latest_recap")
        if latest:
            recap_candidates.append(latest)

        recaps = context.get("recaps") or []
        recap_candidates.extend(recaps)

        for candidate in recap_candidates:
            for attr in ("summary", "recap", "text"):
                value = getattr(candidate, attr, None)
                if value:
                    return value

        active_recap = None
        if hasattr(topic, "active_recaps"):
            active_recap = topic.active_recaps.order_by("-created_at").first()
        if active_recap:
            return getattr(active_recap, "recap", None)
        return None

    def _normalise_whitespace(value):
        return " ".join(value.split())

    recap_text = _extract_recap_text() or default_description
    cleaned_description = strip_tags(recap_text)
    cleaned_description = _normalise_whitespace(cleaned_description)
    if not cleaned_description:
        cleaned_description = default_description
    meta_description = Truncator(cleaned_description).chars(160, truncate="…")

    def _resolve_image():
        topic_obj = context_topic or topic
        image_fields = [
            getattr(topic_obj, "image", None),
            getattr(topic_obj, "thumbnail", None),
        ]

        for field in image_fields:
            if not field:
                continue
            for attr in ("url", "image", "thumbnail"):
                candidate = getattr(field, attr, None)
                if isinstance(candidate, str) and candidate:
                    return candidate, False
                if candidate and hasattr(candidate, "url"):
                    url = getattr(candidate, "url", "")
                    if url:
                        return url, False

        images = context.get("images") or []
        for image in images:
            url = getattr(image, "image_url", None) or getattr(image, "url", None)
            if url:
                return url, False

        return static("logo.png"), True

    image_path, is_default_image = _resolve_image()
    absolute_image_url = request.build_absolute_uri(image_path)

    meta_title = getattr(context_topic, "title", None) or topic.title
    if not meta_title:
        meta_title = _("Semantic News Topic")

    canonical_path = None
    if topic.slug and topic.created_by:
        canonical_path = topic.get_absolute_url()
    if not canonical_path:
        canonical_path = request.get_full_path()

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
        "canonical_url": request.build_absolute_uri(canonical_path),
        "og_image_url": absolute_image_url,
        "open_graph_type": "article",
        "meta_site_name": "Semantic News",
        "twitter_card": "summary"
        if is_default_image
        else "summary_large_image",
    }


@login_required
def topics_detail_edit(request, topic_uuid, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related(
            "events",
            "recaps",
            "texts",
            "images",
            "documents",
            "webpages",
            "youtube_videos",
            "tweets",
            RELATED_ENTITIES_PREFETCH,
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
            Prefetch(
                "topic_related_topics",
                queryset=RelatedTopic.objects.select_related(
                    "related_topic__created_by"
                ).order_by("-created_at"),
                to_attr="prefetched_related_topic_links",
            ),
        ),
        uuid=topic_uuid,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    context = _build_topic_page_context(topic, request.user, edit_mode=True)
    mcp_servers = MCPServer.objects.filter(active=True)
    context["mcp_servers"] = mcp_servers
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user).exclude(
            uuid=topic.uuid
        )
    context["localities"] = get_locality_options()
    context["default_locality_label"] = get_default_locality_label()
    return render(
        request,
        "topics/topics_detail_edit.html",
        context,
    )


@login_required
def topics_detail_preview(request, topic_uuid, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related(
            "events",
            "recaps",
            "texts",
            "images",
            "documents",
            "webpages",
            "youtube_videos",
            "tweets",
            RELATED_ENTITIES_PREFETCH,
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
        ),
        uuid=topic_uuid,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    context = _build_topic_page_context(topic, user=None, edit_mode=False)
    context["is_preview"] = True

    context.update(_build_topic_metadata(request, topic, context))

    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user).exclude(
            uuid=topic.uuid
        )

    return render(
        request,
        "topics/topics_detail.html",
        context,
    )


@login_required
def topic_add_event(request, slug, username, event_uuid):
    topic = get_object_or_404(
        Topic.objects.filter(titles__slug=slug, created_by__username=username).distinct()
    )
    if request.user != topic.created_by:
        return HttpResponseForbidden()

    event = get_object_or_404(Event, uuid=event_uuid)
    RelatedEvent.objects.get_or_create(
        topic=topic,
        event=event,
        defaults={"source": Source.USER},
    )

    return redirect("topics_detail", slug=topic.slug, username=username)


@login_required
def topic_remove_event(request, slug, username, event_uuid):
    topic = get_object_or_404(
        Topic.objects.filter(titles__slug=slug, created_by__username=username).distinct()
    )
    if request.user != topic.created_by:
        return HttpResponseForbidden()

    event = get_object_or_404(Event, uuid=event_uuid)
    RelatedEvent.objects.filter(
        topic=topic,
        event=event,
        is_deleted=False,
    ).update(is_deleted=True)

    return redirect("topics_detail", slug=topic.slug, username=username)


@login_required
def topic_clone(request, slug, username):
    queryset = Topic.objects.prefetch_related(
        "events",
        "contents",
        "recaps",
        "images",
        "keywords",
    ).filter(
        titles__slug=slug,
        created_by__username=username,
    ).distinct()

    original = get_object_or_404(queryset)

    if request.user == original.created_by:
        return HttpResponseForbidden()

    if not _topic_is_visible_to_user(original, request.user):
        raise Http404("Topic not found")

    cloned = original.clone_for_user(request.user)

    return redirect(
        "topics_detail", slug=cloned.slug, username=cloned.created_by.username
    )
