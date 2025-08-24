from django.shortcuts import render, get_object_or_404
from .models import Topic


def topics_detail(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    return render(request, 'topics/topics_detail.html', {
        'topic': topic,
    })
