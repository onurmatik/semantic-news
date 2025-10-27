from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Prefetch
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User

from ..topics.models import Topic, TopicContent
from ..widgets.data.models import TopicDataVisualization
from ..profiles.models import Profile


def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    visualizations_prefetch = Prefetch(
        "data_visualizations",
        queryset=TopicDataVisualization.objects.order_by("-created_at"),
    )

    topics = (
        Topic.objects
        .filter(Q(created_by=user) | Q(contents__created_by=user))
        .filter(status='published')
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .select_related('created_by')
        .prefetch_related('recaps', 'images', visualizations_prefetch)
        .distinct()
        .order_by('-ordering_activity', '-created_at')
    )

    if request.user.is_authenticated:
        topics = topics.exclude(Q(status="draft") & ~Q(created_by=request.user))
    else:
        topics = topics.exclude(status="draft")

    topic_content = TopicContent.objects.filter(created_by=user).select_related(
        'topicarticle__article',
        'topicvideo__video_chunk',
    )

    if request.user.is_authenticated:
        topic_content = topic_content.exclude(
            Q(topic__status="draft") & ~Q(topic__created_by=request.user)
        )
    else:
        topic_content = topic_content.exclude(topic__status='draft')

    profile, c = Profile.objects.get_or_create(user=user)

    return render(request, 'profiles/user_profile.html', {
        'profile_user': user,
        'profile': profile,
        'topics': topics,
        'topic_content': topic_content,
    })

