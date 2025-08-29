from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from pgvector.django import L2Distance

from semanticnews.agenda.models import Event
from .models import Topic, TopicEvent


def topics_detail(request, slug, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related("events", "recaps"),
        slug=slug,
        created_by__username=username,
    )

    related_events = topic.events.all()
    latest_recap = topic.recaps.order_by("-created_at").first()

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
