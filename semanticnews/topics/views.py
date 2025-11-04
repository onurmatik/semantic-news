import json

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils.html import strip_tags
from django.utils.text import Truncator, slugify
from django.utils.translation import gettext as _
from pgvector.django import L2Distance

from semanticnews.agenda.localities import (
    get_default_locality_label,
    get_locality_options,
)
from semanticnews.agenda.models import Event
from semanticnews.widgets.models import Widget
from semanticnews.widgets.rendering import build_renderable_section

from .models import RelatedEntity, RelatedEvent, RelatedTopic, Source, Topic


RELATED_ENTITIES_PREFETCH = Prefetch(
    "related_entities",
    queryset=RelatedEntity.objects.filter(is_deleted=False)
    .select_related("entity")
    .order_by("-created_at"),
    to_attr="prefetched_related_entities",
)


def _build_renderable_sections(topic, *, edit_mode=False):
    """Return section descriptors prepared for template rendering."""

    sections = topic.sections_ordered if edit_mode else topic.active_sections

    renderables = []
    for index, section in enumerate(sections, start=1):
        descriptor = build_renderable_section(section, edit_mode=edit_mode)
        descriptor.key = f"section:{getattr(section, 'id', None) or index}"
        renderables.append(descriptor)

    return renderables


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

    topics = (
        Topic.objects.filter(status="published")
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .select_related("created_by")
        .prefetch_related("recaps", "images", "sections__widget")
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
        "images",
        "sections__widget",
        RELATED_ENTITIES_PREFETCH,
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


def _build_topic_module_context(topic, user=None, *, edit_mode=False):
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
        "related_topic_links": active_related_topic_links,
        "related_topics": related_topics,
        "sections": _build_renderable_sections(topic, edit_mode=edit_mode),
    }


def _build_topic_page_context(topic, user=None, *, edit_mode=False):
    context = _build_topic_module_context(topic, user, edit_mode=edit_mode)
    context["edit_mode"] = edit_mode

    if edit_mode:
        widgets = list(Widget.objects.all().order_by("name"))
        catalog: list[dict[str, object]] = []
        for widget in widgets:
            key = slugify(widget.name or "")
            if not key:
                key = f"widget-{widget.pk or len(catalog) + 1}"
            catalog.append(
                {
                    "id": widget.id,
                    "name": widget.name,
                    "key": key,
                    "template": widget.template or "",
                    "response_format": widget.response_format or {},
                    "actions": [w.name for w in widget.actions.all()],
                }
            )
        context["widget_catalog"] = catalog
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
        Topic,
        uuid=topic_uuid,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    context = _build_topic_page_context(topic, request.user, edit_mode=True)
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
