from django.shortcuts import render
from django.db.models import Prefetch
from pgvector.django import L2Distance

from .agenda.models import Event
from .topics.models import Topic
from .widgets.data.models import TopicDataVisualization
from .openai import OpenAI


def home(request):
    recent_events = Event.objects.filter(status='published').order_by('-date')[:5]
    visualizations_prefetch = Prefetch(
        "data_visualizations",
        queryset=TopicDataVisualization.objects.order_by("-created_at"),
    )
    context = {
        'events': recent_events,
        'topics': (
            Topic.objects.filter(status='published')
            .select_related('created_by', 'latest_publication')
            .prefetch_related('recaps', 'images', visualizations_prefetch)
        ),
    }
    if request.user.is_authenticated:
        context['user_topics'] = Topic.objects.filter(created_by=request.user)
    return render(request, 'home.html', context)


def search_results(request):
    """Search for topics and events similar to the query string."""

    query = request.GET.get("q", "").strip()
    topics = Topic.objects.none()
    events = Event.objects.none()

    if query:
        with OpenAI() as client:
            embedding = (
                client.embeddings.create(
                    model="text-embedding-3-small",
                    input=query,
                )
                .data[0]
                .embedding
            )

        visualizations_prefetch = Prefetch(
            "data_visualizations",
            queryset=TopicDataVisualization.objects.order_by("-created_at"),
        )

        topics = (
            Topic.objects.filter(status="published")
            .exclude(embedding__isnull=True)
            .select_related("created_by", "latest_publication")
            .prefetch_related("recaps", "images", visualizations_prefetch)
            .annotate(distance=L2Distance("embedding", embedding))
            .order_by("distance")[:5]
        )

        events = (
            Event.objects.filter(status="published")
            .exclude(embedding__isnull=True)
            .annotate(distance=L2Distance("embedding", embedding))
            .order_by("distance")[:5]
        )

    context = {
        "search_query": query,
        "topics": topics,
        "events": events,
    }
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user)

    return render(request, "search_results.html", context)
