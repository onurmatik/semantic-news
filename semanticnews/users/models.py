from django.db import models
from openai import OpenAI
from pgvector.django import VectorField, HnswIndex
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    embedding = VectorField(dimensions=1536, blank=True, null=True)

    class Meta:
        indexes = [
            HnswIndex(
                name='searchterm_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.term,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding


class UserBookmark(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'topic'], name='unique_user_topic_bookmark')
        ]
