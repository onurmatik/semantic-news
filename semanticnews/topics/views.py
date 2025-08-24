from django.shortcuts import render, get_object_or_404
from .models import Topic


def topics_detail(request, slug, username):
    topic = get_object_or_404(
        Topic, slug=slug,
        created_by__username=username,
    )
    return render(request, 'topics/topics_detail.html', {
        'topic': topic,
    })
