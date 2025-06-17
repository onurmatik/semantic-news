"""
Celery tasks for the YouTube app.
"""
from time import sleep

from celery import shared_task, group, chord
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from .models import Channel, Video, VideoTranscript, VideoTranscriptChunk
from ..topics.models import TopicVideo
from ..utils import get_relevance


@shared_task
def fetch_channel_content(channel_id):
    """
    Fetch latest videos and stats for a single YouTube channel.

    :param channel_id: Primary key of the Channel to fetch.
    """
    try:
        channel = Channel.objects.get(pk=channel_id)
    except Channel.DoesNotExist:
        return f"Channel {channel_id} does not exist"

    channel.fetch_channel_content()
    return f"Fetched Channel {channel_id}"


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},  # retry 2 more times, 30s apart
    retry_backoff=True,  # Exponential backoff
)
def fetch_transcript(self, video_pk: int):
    """
    Fetch the transcript for one video.
    Retries up to 3 times (initial + 2 retries).
    If still failing, marks all TopicVideos as processed.
    """
    video = Video.objects.get(pk=video_pk)
    try:
        video.fetch_transcript()
    except Exception as exc:
        print(f"Retry for {video.video_id}. Exception: {exc}")
        if self.request.retries >= self.max_retries:
            # Mark all related TopicVideos as processed after final failure
            TopicVideo.objects.filter(video=video, processed=False).update(processed=True)
            print(f"Transcript failed for {video.video_id} after {self.max_retries + 1} attempts. Marked TopicVideos as processed.")
            return  # DO NOT RAISE, just end the task
        raise  # propagate, Celery handles the retry


@shared_task(bind=True, max_retries=3, default_retry_delay=2)
def revise_chunk_text(self, chunk_pk: int):
    """
    Revise the chunk text for the given VideoTranscriptChunk instance and compute its embedding.
    """
    try:
        chunk = VideoTranscriptChunk.objects.get(pk=chunk_pk)
    except ObjectDoesNotExist:
        # Wait for transaction to commit, then retry
        try:
            self.retry(countdown=2)
        except self.MaxRetriesExceededError:
            print(f"Chunk {chunk_pk} still does not exist after retries.")
            return
        return

    chunk.revise_text()
    # If revise_text() didn’t set embedding, force it
    emb = chunk.embedding
    if emb is None or (hasattr(emb, '__len__') and len(emb) == 0):
        chunk.embedding = chunk.get_embedding()
        chunk.save(update_fields=['embedding'])


@shared_task
def link_video_to_topic(_header_results, video_id: int, threshold: float = 0.5):
    """
    Chord callback: once all chunks have been revised & embedded,
    pick the best one for each pending TopicVideo and mark it processed.
    """
    print(f"link_video_to_topic for video_id={video_id} (threshold={threshold})")
    try:
        transcript = VideoTranscript.objects.get(video_id=video_id)
        all_chunks = list(transcript.chunks.all())
        print(f"  Found {len(all_chunks)} chunks")
    except VideoTranscript.DoesNotExist:
        print(f"  No VideoTranscript exists for {video_id}")
        TopicVideo.objects.filter(video_id=video_id, processed=False).update(processed=True)
        return

    for tv in TopicVideo.objects.filter(video_id=video_id, processed=False):
        print(f"  Processing TopicVideo {tv.pk} for topic {tv.topic_id}")
        scored = [
            (c, get_relevance(c.embedding, tv.topic.embedding) or 0)
            for c in all_chunks
        ]
        print(f"    Chunks scored: {[score for _, score in scored]}")
        if not scored:
            print(f"    No chunks scored, marking processed")
            tv.processed = True
            tv.save(update_fields=['processed'])
            continue
        best_chunk, best_score = max(scored, key=lambda x: x[1])
        print(f"    Best score: {best_score}")
        if best_score < threshold:
            print(f"    Best score below threshold, marking processed")
            tv.processed = True
            tv.save(update_fields=['processed'])
            continue

        print(f"    Relating video_chunk {best_chunk.pk} to TopicVideo {tv.pk}")
        tv.video_chunk = best_chunk
        tv.processed = True
        tv.embedding = best_chunk.embedding
        tv.save(update_fields=['video_chunk', 'processed', 'embedding'])


@shared_task
def create_transcript_chunks(transcript_pk: int, size=3000, overlap=1000):
    """
    Chunk the transcript → then run revise_chunk_text on each chunk →
    finally invoke link_video_to_topic once all are done.
    Triggered from VideoTranscript.save().
    """
    # FIXME: temporary patch
    sleep(1)
    vt = VideoTranscript.objects.get(pk=transcript_pk)
    vt.create_chunks(size=size, overlap=overlap)

    # collect all new chunk IDs
    chunk_ids = list(
        VideoTranscriptChunk.objects
            .filter(transcript_id=transcript_pk)
            .values_list('pk', flat=True)
    )
    video_id = vt.video_id

    def schedule_chord():
        chord(
            group(revise_chunk_text.s(pk) for pk in chunk_ids),
            link_video_to_topic.s(video_id)
        ).apply_async()

    transaction.on_commit(schedule_chord)


@shared_task
def retry_failed_transcripts():
    """
    Retry fetching transcripts of fetched videos, which is the case for videos that have not premiered yet.
    """
    grace_hours = 24
    videos = Video.objects.filter(
        published_at__lte=timezone.now() - timezone.timedelta(hours=grace_hours)
    ).filter(videotranscript__isnull=True).only("id", "video_id")

    if not videos:
        return

    group(fetch_transcript.s(v.pk) for v in videos).apply_async()
