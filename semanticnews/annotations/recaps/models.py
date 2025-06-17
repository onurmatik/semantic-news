from django.db import models


class TopicRecap(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='recaps')
    recap = models.TextField()
    recap_en = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recap for {self.topic}"
