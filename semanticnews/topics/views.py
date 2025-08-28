from django.shortcuts import render, get_object_or_404
from pgvector.django import L2Distance

from semanticnews.agenda.models import Event
from .models import Topic


def topics_detail(request, slug, username):
    topic = get_object_or_404(
        Topic.objects.prefetch_related("events"),
        slug=slug,
        created_by__username=username,
    )

    related_events = topic.events.all()

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
        },
    )
