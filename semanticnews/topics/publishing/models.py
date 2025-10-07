from django.conf import settings
from django.db import models
from django.utils import timezone


class TopicPublication(models.Model):
    """Snapshot of a topic captured at publish time."""

    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='publications',
    )
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='topic_publications',
    )
    layout_snapshot = models.JSONField(default=dict)
    context_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'
        ordering = ('-published_at', 'id')

    def __str__(self):
        return f"Publication for {self.topic} at {self.published_at:%Y-%m-%d %H:%M:%S}"


class TopicPublicationModule(models.Model):
    """Serialized module payload stored for a publication."""

    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='modules',
    )
    module_key = models.CharField(max_length=50)
    placement = models.CharField(max_length=20)
    display_order = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict)

    class Meta:
        app_label = 'topics'
        ordering = ('placement', 'display_order', 'id')

    def __str__(self):
        return f"{self.module_key} ({self.placement}) for {self.publication_id}"


class TopicPublishedImage(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_images',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    image = models.CharField(max_length=500, blank=True)
    thumbnail = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedText(models.Model):
    """Snapshot of a text block included in a publication."""

    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_texts',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedRecap(models.Model):
    """Snapshot of the recap that was live at publish time."""

    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_recaps',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    recap = models.TextField(blank=True)
    status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedDocument(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_documents',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedWebpage(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_webpages',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedYoutubeVideo(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_youtube_videos',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    url = models.URLField(blank=True, null=True)
    video_id = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    thumbnail = models.URLField(blank=True, null=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedTweet(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_tweets',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    tweet_id = models.CharField(max_length=50)
    url = models.URLField()
    html = models.TextField()
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedRelation(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_relations',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    relations = models.JSONField(default=list)
    status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedData(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_data',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    data = models.JSONField(default=dict)
    sources = models.JSONField(default=list)
    explanation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedDataInsight(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_data_insights',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    insight = models.TextField()
    source_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedDataVisualization(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_data_visualizations',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    chart_type = models.CharField(max_length=50)
    chart_data = models.JSONField(default=dict)
    insight_text = models.TextField(blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')


class TopicPublishedEvent(models.Model):
    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='published_events',
    )
    original_id = models.PositiveIntegerField(null=True, blank=True)
    event_id = models.PositiveIntegerField()
    role = models.CharField(max_length=20, blank=True)
    significance = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')
