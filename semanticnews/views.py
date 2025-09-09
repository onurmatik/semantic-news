from django.shortcuts import render
from .agenda.models import Event
from .topics.models import Topic


def home(request):
    recent_events = Event.objects.filter(status='published').order_by('-date')[:5]
    context = {
        'events': recent_events,
        'topics': Topic.objects.filter(status='published'),
    }
    if request.user.is_authenticated:
        context['user_topics'] = Topic.objects.filter(created_by=request.user)
    return render(request, 'home.html', context)
