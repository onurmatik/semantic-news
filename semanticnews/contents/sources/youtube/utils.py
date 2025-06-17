import random

from django.conf import settings
from youtube_transcript_api import (
    TranscriptsDisabled, NoTranscriptFound, AgeRestricted, VideoUnplayable, VideoUnavailable,
    InvalidVideoId, RequestBlocked, IpBlocked, YouTubeRequestFailed, NotTranslatable,
    TranslationLanguageNotAvailable, FailedToCreateConsentCookie, CouldNotRetrieveTranscript, YouTubeTranscriptApi
)
from django.utils.translation import gettext_lazy as _


PROXIES_LIST = None
if settings.PROXY_ENDPOINTS:
    PROXIES_LIST = [
        {"http": url, "https": url}
        for url in settings.PROXY_ENDPOINTS
    ]


def list_youtube_transcripts(video_id):
    """
    Try to list YouTube transcripts, using a random proxy.
    """
    proxies = random.choice(PROXIES_LIST) if PROXIES_LIST else None
    return YouTubeTranscriptApi.list_transcripts(
        video_id,
        proxies=proxies,
    )


def map_transcript_exception(exc) -> (str, str):
    # Returns (transcript_status, user_message)
    if isinstance(exc, (TranscriptsDisabled,)):
        return "none", _("This video has no subtitles available.")
    elif isinstance(exc, (NoTranscriptFound,)):
        return "none", _("No transcript found for this video.")
    elif isinstance(exc, (NotTranslatable, TranslationLanguageNotAvailable)):
        return "none", _("Transcript translation is not available for this language.")
    elif isinstance(exc, (AgeRestricted,)):
        return "error", _("This video is age-restricted. Transcript cannot be retrieved.")
    elif isinstance(exc, (VideoUnplayable, VideoUnavailable)):
        return "error", _("This video is unavailable or cannot be played.")
    elif isinstance(exc, (InvalidVideoId,)):
        return "error", _("Invalid YouTube video ID.")
    elif isinstance(exc, (RequestBlocked, IpBlocked)):
        return "error", _("YouTube is blocking requests from our IP. Please try again later.")
    elif isinstance(exc, (YouTubeRequestFailed,)):
        return "error", _("YouTube request failed. Please try again later.")
    elif isinstance(exc, (FailedToCreateConsentCookie,)):
        return "error", _("Unable to fetch transcript due to cookie/consent issue.")
    elif isinstance(exc, CouldNotRetrieveTranscript):
        # fallback for any other "could not retrieve"
        return "error", _("Could not retrieve transcript for this video.")
    else:
        return "error", _("An unknown error occurred when fetching transcript.")
