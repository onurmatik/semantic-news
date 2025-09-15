from django.db import models


class TopicSocialEmbed(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='social_embeds')
    provider = models.CharField(max_length=50)
    url = models.URLField()
    html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"{self.provider} embed for {self.topic.title}"
