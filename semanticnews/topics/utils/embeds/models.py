from django.db import models


class TopicTweet(models.Model):
    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='tweets'
    )
    tweet_id = models.CharField(max_length=50, db_index=True)
    url = models.URLField()
    html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "tweet_id"), name="unique_topic_tweet"
            )
        ]

    def __str__(self):
        return f"Tweet {self.tweet_id} for {self.topic.title}"


class TopicYoutubeVideo(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='youtube_videos')
    url = models.URLField(blank=True, null=True)
    video_id = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    thumbnail = models.URLField(blank=True, null=True)
    published_at = models.DateTimeField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In progress"),
            ("finished", "Finished"),
            ("error", "Error"),
        ],
        default="in_progress",
    )
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(blank=True, null=True, max_length=20)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"{self.title} for {self.topic.title}"
