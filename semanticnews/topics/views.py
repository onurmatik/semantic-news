from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from pgvector.django import L2Distance
import json

from semanticnews.agenda.models import Event
from .models import Topic
from .utils.timeline.models import TopicEvent
from .utils.mcps.models import MCPServer


def topics_detail(request, slug, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related(
            "events",
            "recaps",
            "narratives",
            "images",
            "documents",
            "webpages",
            "youtube_videos",
            "tweets",
            "entity_relations",
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
        ),
        slug=slug,
        created_by__username=username,
    )

    related_events = topic.events.all()

    # Only the “finished/latest” versions are used on the read-only page
    latest_narrative = (
        topic.narratives.filter(status="finished").order_by("-created_at").first()
    )
    latest_recap = (
        topic.recaps.filter(status="finished").order_by("-created_at").first()
    )
    latest_relation = (
        topic.entity_relations.filter(status="finished").order_by("-created_at").first()
    )

    documents = list(topic.documents.all())
    webpages = list(topic.webpages.all())

    latest_data = topic.datas.order_by("-created_at").first()
    datas = topic.datas.order_by("-created_at")  # used by data card
    data_insights = topic.data_insights.order_by("-created_at")
    data_visualizations = topic.data_visualizations.order_by("-created_at")

    youtube_video = topic.youtube_videos.order_by("-created_at").first()
    tweets = topic.tweets.order_by("-created_at")

    if latest_relation:
        relations_json = json.dumps(latest_relation.relations, separators=(",", ":"))
        relations_json_pretty = json.dumps(latest_relation.relations, indent=2)
    else:
        relations_json = ""
        relations_json_pretty = ""

    context = {
        "topic": topic,
        "related_events": related_events,
        "latest_recap": latest_recap,
        "latest_relation": latest_relation,
        "relations_json": relations_json,
        "relations_json_pretty": relations_json_pretty,
        "latest_narrative": latest_narrative,
        "latest_data": latest_data,
        "datas": datas,
        "data_insights": data_insights,
        "data_visualizations": data_visualizations,
        "youtube_video": youtube_video,
        "tweets": tweets,
        "documents": documents,
        "webpages": webpages,
    }

    return render(request, "topics/topics_detail.html", context)


@login_required
def topics_detail_edit(request, slug, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related(
            "events",
            "recaps",
            "narratives",
            "images",
            "documents",
            "webpages",
            "youtube_videos",
            "tweets",
            "entity_relations",
            "datas",
            "data_insights__sources",
            "data_visualizations__insight",
        ),
        slug=slug,
        created_by__username=username,
    )

    if request.user != topic.created_by or topic.status == "archived":
        return HttpResponseForbidden()

    related_events = topic.events.all()
    current_narrative = topic.narratives.order_by("-created_at").first()
    latest_narrative = (
        topic.narratives.filter(status="finished").order_by("-created_at").first()
    )
    current_recap = topic.recaps.order_by("-created_at").first()
    latest_recap = (
        topic.recaps.filter(status="finished").order_by("-created_at").first()
    )
    current_relation = topic.entity_relations.order_by("-created_at").first()
    latest_relation = (
        topic.entity_relations.filter(status="finished")
        .order_by("-created_at")
        .first()
    )
    documents = list(topic.documents.all())
    webpages = list(topic.webpages.all())
    latest_data = topic.datas.order_by("-created_at").first()
    datas = topic.datas.order_by("-created_at")
    data_insights = topic.data_insights.order_by("-created_at")
    data_visualizations = topic.data_visualizations.order_by("-created_at")
    youtube_video = topic.youtube_videos.order_by("-created_at").first()
    tweets = topic.tweets.order_by("-created_at")
    if latest_relation:
        relations_json = json.dumps(
            latest_relation.relations, separators=(",", ":")
        )
        relations_json_pretty = json.dumps(latest_relation.relations, indent=2)
    else:
        relations_json = ""
        relations_json_pretty = ""
    mcp_servers = MCPServer.objects.filter(active=True)

    if topic.embedding is not None:
        suggested_events = (
            Event.objects.exclude(topics=topic)
            .exclude(embedding__isnull=True)
            .annotate(distance=L2Distance("embedding", topic.embedding))
            .order_by("distance")[:5]
        )
    else:
        suggested_events = Event.objects.none()

    context = {
        "topic": topic,
        "related_events": related_events,
        "suggested_events": suggested_events,
        "current_recap": current_recap,
        "latest_recap": latest_recap,
        "current_relation": current_relation,
        "latest_relation": latest_relation,
        "relations_json": relations_json,
        "relations_json_pretty": relations_json_pretty,
        "current_narrative": current_narrative,
        "latest_narrative": latest_narrative,
        "mcp_servers": mcp_servers,
        "latest_data": latest_data,
        "datas": datas,
        "data_insights": data_insights,
        "data_visualizations": data_visualizations,
        "youtube_video": youtube_video,
        "tweets": tweets,
        "documents": documents,
        "webpages": webpages,
    }
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user).exclude(
            uuid=topic.uuid
        )
    return render(
        request,
        "topics/topics_detail_edit.html",
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
    TopicEvent.objects.filter(topic=topic, event=event).delete()

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

    cloned = original.clone_for_user(request.user)

    return redirect(
        "topics_detail", slug=cloned.slug, username=cloned.created_by.username
    )
