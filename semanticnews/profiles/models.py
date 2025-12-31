from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.first_name.strip() or self.user.username


class TopicBookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='bookmarked_by')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'topic'], name='unique_user_topic_bookmark')
        ]


class UserReference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reference_links",
    )
    reference = models.ForeignKey(
        "references.Reference",
        on_delete=models.CASCADE,
        related_name="user_links",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reference"],
                name="unique_user_reference",
            )
        ]
