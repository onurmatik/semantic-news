from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.translation import gettext as _

from .forms import DisplayNameForm
from .models import Profile
from ..topics.models import Topic, TopicContent


def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    topics = (Topic.objects
              .filter(Q(created_by=user) |
                      Q(contents__added_by=user))
              .exclude(status='r').distinct()).order_by('-updated_at')

    topic_content = TopicContent.objects.filter(added_by=user).select_related(
        'topicarticle__article',
        'topicvideo__video_chunk',
    )

    profile, c = Profile.objects.get_or_create(user=user)

    return render(request, 'profiles/user_profile.html', {
        'profile_user': user,
        'profile': profile,
        'topics': topics,
        'topic_content': topic_content,
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
