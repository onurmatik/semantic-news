from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from semanticnews.contents.sources.youtube.models import Video, Channel


def video_detail(request, video_id):
    video = get_object_or_404(Video, video_id=video_id)

    return render(request, 'youtube/video_detail.html', {
        'video': video,
        'transcript': video.videotranscript_set.first(),
    })


@login_required
def dashboard(request):
    channels = Channel.objects.filter(id__in=request.user.userchannel_set.all().values_list('id', flat=True))
    return render(request, 'dashboard/dashboard.html', {
        'channels': channels,
    })
