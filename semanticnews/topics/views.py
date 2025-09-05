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
        Topic.objects.prefetch_related("events", "recaps"),
        slug=slug,
        created_by__username=username,
    )

    related_events = topic.events.all()
    latest_recap = topic.recaps.order_by("-created_at").first()
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

    return render(
        request,
        "topics/topics_detail.html",
        {
            "topic": topic,
            "related_events": related_events,
            "suggested_events": suggested_events,
            "latest_recap": latest_recap,
            "mcp_servers": mcp_servers,
        },
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

    cloned = Topic.objects.create(
        title=original.title,
        slug=original.slug,
        embedding=original.embedding,
        based_on=original,
        created_by=request.user,
        status="draft",
    )

    for te in TopicEvent.objects.filter(topic=original):
        TopicEvent.objects.create(
            topic=cloned,
            event=te.event,
            role=te.role,
            source=te.source,
            relevance=te.relevance,
            pinned=te.pinned,
            rank=te.rank,
            created_by=request.user,
        )

    for tc in TopicContent.objects.filter(topic=original):
        TopicContent.objects.create(
            topic=cloned,
            content=tc.content,
            role=tc.role,
            source=tc.source,
            relevance=tc.relevance,
            pinned=tc.pinned,
            rank=tc.rank,
            created_by=request.user,
        )

    for recap in original.recaps.all():
        TopicRecap.objects.create(topic=cloned, recap=recap.recap)

    for image in original.images.all():
        TopicImage.objects.create(
            topic=cloned,
            image=image.image,
            thumbnail=image.thumbnail,
        )

    for tk in TopicEntity.objects.filter(topic=original):
        TopicEntity.objects.create(
            topic=cloned,
            keyword=tk.keyword,
            relevance=tk.relevance,
            created_by=request.user,
        )

    return redirect(
        "topics_detail", slug=cloned.slug, username=cloned.created_by.username
    )
