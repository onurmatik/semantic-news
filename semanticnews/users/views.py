from django.shortcuts import render, get_object_or_404


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

