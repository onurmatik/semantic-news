from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from pgvector.django import L2Distance

from semanticnews.agenda.models import Event
from .models import Topic, TopicEvent, TopicContent, TopicEntity
from .utils.recaps.models import TopicRecap
from .utils.images.models import TopicImage
from .utils.mcps.models import MCPServer


def topics_detail(request, slug, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related("events", "recaps", "images"),
        slug=slug,
        created_by__username=username,
    )

    related_events = topic.events.all()
    current_recap = topic.recaps.order_by("-created_at").first()
    latest_recap = (
        topic.recaps.filter(status="finished").order_by("-created_at").first()
    )
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
        "mcp_servers": mcp_servers,
    }
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user).exclude(uuid=topic.uuid)
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
