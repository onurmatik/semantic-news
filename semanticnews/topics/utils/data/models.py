from django.conf import settings
from django.db import models



class TopicDataRequest(models.Model):
    """Track asynchronous data fetch/search requests for a topic."""

    class Mode(models.TextChoices):
        URL = "url", "URL"
        SEARCH = "search", "Search"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    topic = models.ForeignKey(
        "topics.Topic",
        on_delete=models.CASCADE,
        related_name="data_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="topic_data_requests",
    )
    mode = models.CharField(max_length=20, choices=Mode.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    task_id = models.CharField(max_length=255, blank=True, null=True)
    input_payload = models.JSONField(default=dict)
    result = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "topics"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Data request {self.id} for {self.topic}"


class TopicData(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='datas')
    url = models.URLField()
    name = models.CharField(max_length=200, blank=True, null=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"{self.name or 'Data'} for {self.topic}"


class TopicDataInsight(models.Model):
    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='data_insights'
    )
    insight = models.TextField()
    sources = models.ManyToManyField('TopicData', related_name='insights')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Insight for {self.topic}"


class TopicDataVisualization(models.Model):
    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='data_visualizations'
    )
    insight = models.ForeignKey(
        TopicDataInsight, on_delete=models.SET_NULL, null=True, blank=True, related_name='visualizations'
    )
    chart_type = models.CharField(max_length=50)
    chart_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Visualization for {self.topic}"
