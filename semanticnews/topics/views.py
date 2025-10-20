from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from pgvector.django import L2Distance
import json

from django.db.models import Prefetch

from semanticnews.agenda.models import Event
from semanticnews.agenda.localities import (
    get_default_locality_label,
    get_locality_options,
)

from .models import Topic, TopicModuleLayout
from .layouts import annotate_module_content, get_layout_for_mode
from .publishing.service import build_publication_context, build_publication_modules
from .utils.timeline.models import TopicEvent
from .utils.data.models import TopicDataVisualization
from .utils.mcps.models import MCPServer


@login_required
def topic_create(request):
    """Legacy endpoint retained for backwards compatibility.

    Previously, this view created a draft topic and redirected the user to the
    edit page. The creation flow now happens client-side via a modal dialog, so
    this view simply redirects authenticated users back to the topics list
    without creating a new topic. This prevents accidental topic creation when
    the legacy URL is visited directly or linked from outdated clients.
    """

    return redirect("topics_list")


def _topic_is_visible_to_user(topic, user):
    """Return True if the topic should be visible to the given user."""

    if topic.status != "draft":
        return True

    if topic.created_by_id is None:
        return False

    return user.is_authenticated and user == topic.created_by


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
        raise Http404("Topic does not have a slug yet.")

    return redirect("topics_detail", slug=topic.slug, username=username)


def topics_list(request):
    """Display the most recently updated published topics."""

    visualizations_prefetch = Prefetch(
        "data_visualizations",
        queryset=TopicDataVisualization.objects.order_by("-created_at"),
    )

    topics = (
        Topic.objects.filter(status="published")
        .select_related("created_by", "latest_publication")
        .prefetch_related("recaps", "images", visualizations_prefetch)
        .order_by("-updated_at", "-created_at")
    )

    context = {"topics": topics}
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user).order_by(
            "-updated_at"
        )

    return render(request, "topics/topics_list.html", context)


def topics_detail(request, slug, username):
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
            "entity_relations",
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
            "module_layouts",
        ),
        slug=slug,
        created_by__username=username,
    )

    if not _topic_is_visible_to_user(topic, request.user):
        raise Http404("Topic not found")

    publication = topic.latest_publication

    if publication:
        context = build_publication_context(topic, publication)
        modules = build_publication_modules(publication, context)
        primary_modules = modules.get(TopicModuleLayout.PLACEMENT_PRIMARY, [])
        sidebar_modules = modules.get(TopicModuleLayout.PLACEMENT_SIDEBAR, [])
        annotate_module_content(primary_modules, context)
        annotate_module_content(sidebar_modules, context)
        context["primary_modules"] = primary_modules
        context["sidebar_modules"] = sidebar_modules
        return render(request, "topics/topics_detail.html", context)

    context = {
        "topic": topic,
        "primary_modules": [],
        "sidebar_modules": [],
        "is_unpublished": True,
    }

    return render(request, "topics/topics_detail.html", context)


def _build_topic_module_context(topic):
    """Collect related objects used to render topic modules."""

    related_events = topic.active_events
    current_recap = topic.active_recaps.order_by("-created_at").first()
    latest_recap = (
        topic.active_recaps.filter(status="finished")
        .order_by("-created_at")
        .first()
    )
    current_relation = topic.active_entity_relations.order_by("-created_at").first()
    latest_relation = (
        topic.active_entity_relations.filter(status="finished")
        .order_by("-created_at")
        .first()
    )
    documents = list(topic.active_documents)
    webpages = list(topic.active_webpages)
    latest_data = topic.active_datas.order_by("-created_at").first()
    datas = topic.active_datas.order_by("-created_at")
    data_insights = topic.active_data_insights.order_by("-created_at")
    data_visualizations = topic.active_data_visualizations.order_by("-created_at")
    youtube_video = topic.active_youtube_videos.order_by("-created_at").first()
    tweets = topic.active_tweets.order_by("-created_at")

    if latest_relation:
        relations_json = json.dumps(latest_relation.relations, separators=(",", ":"))
        relations_json_pretty = json.dumps(latest_relation.relations, indent=2)
    else:
        relations_json = ""
        relations_json_pretty = ""

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
        "current_relation": current_relation,
        "latest_relation": latest_relation,
        "relations_json": relations_json,
        "relations_json_pretty": relations_json_pretty,
        "latest_data": latest_data,
        "datas": datas,
        "data_insights": data_insights,
        "data_visualizations": data_visualizations,
        "youtube_video": youtube_video,
        "tweets": tweets,
        "documents": documents,
        "webpages": webpages,
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
            "entity_relations",
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
            "module_layouts",
        ),
        uuid=topic_uuid,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    context = _build_topic_module_context(topic)
    mcp_servers = MCPServer.objects.filter(active=True)

    layout = get_layout_for_mode(topic, mode="edit")
    primary_modules = layout.get(TopicModuleLayout.PLACEMENT_PRIMARY, [])
    sidebar_modules = layout.get(TopicModuleLayout.PLACEMENT_SIDEBAR, [])

    context.update(
        {
            "mcp_servers": mcp_servers,
            "layout_update_url": f"/api/topics/{topic.uuid}/layout",
        }
    )

    annotate_module_content(primary_modules, context)
    annotate_module_content(sidebar_modules, context)
    context["primary_modules"] = primary_modules
    context["sidebar_modules"] = sidebar_modules
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
            "entity_relations",
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
            "module_layouts",
        ),
        uuid=topic_uuid,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    context = _build_topic_module_context(topic)

    layout = get_layout_for_mode(topic, mode="detail")
    primary_modules = layout.get(TopicModuleLayout.PLACEMENT_PRIMARY, [])
    sidebar_modules = layout.get(TopicModuleLayout.PLACEMENT_SIDEBAR, [])

    annotate_module_content(primary_modules, context)
    annotate_module_content(sidebar_modules, context)
    context["primary_modules"] = primary_modules
    context["sidebar_modules"] = sidebar_modules
    context["is_preview"] = True

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
    topic = get_object_or_404(Topic, slug=slug, created_by__username=username)
    if request.user != topic.created_by:
        return HttpResponseForbidden()

    event = get_object_or_404(Event, uuid=event_uuid)
    TopicEvent.objects.get_or_create(
        topic=topic,
        event=event,
        defaults={"created_by": request.user},
    )

    return redirect("topics_detail", slug=topic.slug, username=username)


@login_required
def topic_remove_event(request, slug, username, event_uuid):
    topic = get_object_or_404(Topic, slug=slug, created_by__username=username)
    if request.user != topic.created_by:
        return HttpResponseForbidden()

    event = get_object_or_404(Event, uuid=event_uuid)
    TopicEvent.objects.filter(
        topic=topic,
        event=event,
        is_deleted=False,
    ).update(is_deleted=True)
    from .signals import touch_topic

    touch_topic(topic.pk)

    return redirect("topics_detail", slug=topic.slug, username=username)


@login_required
def topic_clone(request, slug, username):
    original = get_object_or_404(
        Topic.objects.prefetch_related(
            "events",
            "contents",
            "recaps",
            "images",
            "keywords",
        ),
        slug=slug,
        created_by__username=username,
    )

    if request.user == original.created_by:
        return HttpResponseForbidden()

    if not _topic_is_visible_to_user(original, request.user):
        raise Http404("Topic not found")

    cloned = original.clone_for_user(request.user)

    return redirect(
        "topics_detail", slug=cloned.slug, username=cloned.created_by.username
    )
