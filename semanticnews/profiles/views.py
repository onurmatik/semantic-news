from django.contrib.auth.decorators import login_required
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db.models import Q, Count, Max, Value, DateTimeField, Prefetch
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.translation import gettext as _

from .forms import DisplayNameForm
from .models import Profile
from ..topics.models import Topic


def user_list(request):
    """Display active users ordered by their recent contributions."""

    epoch = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
    if not settings.USE_TZ:
        epoch = epoch.replace(tzinfo=None)

    users = (
        User.objects.filter(is_active=True)
        .annotate(
            topics_count=Count(
                "topics",
                filter=Q(topics__status="published"),
                distinct=True,
            ),
            events_count=Count("entries", distinct=True),
            latest_topic_activity=Max(
                Coalesce("topics__last_published_at", "topics__created_at")
            ),
            latest_event_activity=Max("entries__updated_at"),
        )
        .annotate(
            last_activity=Greatest(
                Coalesce(
                    "latest_topic_activity",
                    Value(epoch, output_field=DateTimeField()),
                ),
                Coalesce(
                    "latest_event_activity",
                    Value(epoch, output_field=DateTimeField()),
                ),
                Coalesce(
                    "last_login",
                    Value(epoch, output_field=DateTimeField()),
                ),
                Coalesce(
                    "date_joined",
                    Value(epoch, output_field=DateTimeField()),
                ),
            )
        )
        .order_by("-last_activity", "username")
    )

    recent_topics = (
        Topic.objects.filter(status="published")
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .select_related("created_by")
        .order_by("-ordering_activity", "-created_at")[:5]
    )

    context = {
        "users": users,
        "recent_topics": recent_topics,
    }

    return render(request, "profiles/user_list.html", context)


def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    topics = (
        Topic.objects
        .filter(created_by=user)
        .select_related("created_by")
        .annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
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


@login_required
def profile_settings(request):
    """
    Edit the current user's display name.
    """
    user = request.user

    if request.method == "POST":
        form = DisplayNameForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your display name has been updated."))
            return redirect("user_profile", username=user.username)
        else:
            for field, errs in form.errors.items(): # (__all__ for non-field errors)
                for err in errs:
                    messages.error(
                        request,
                        f"{form.fields.get(field).label if field != '__all__' else ''}: {err}"
                    )
    else:
        form = DisplayNameForm(instance=user)

    return render(request, "profiles/profile_settings.html", {"form": form})
