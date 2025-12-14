from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User

from ..topics.models import Topic
from ..profiles.models import Profile


def user_profile(request, username):
    user = get_object_or_404(User, username=username)

    topics = (
        Topic.objects
        .filter(created_by=user)
        .filter(status='published')
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .select_related('created_by')
        .prefetch_related('recaps', 'images')
        .distinct()
        .order_by('-ordering_activity', '-created_at')
    )

    if request.user.is_authenticated:
        topics = topics.exclude(Q(status="draft") & ~Q(created_by=request.user))
    else:
        topics = topics.exclude(status="draft")

    profile, c = Profile.objects.get_or_create(user=user)

    return render(request, 'profiles/user_profile.html', {
        'profile_user': user,
        'profile': profile,
        'topics': topics,
    })
