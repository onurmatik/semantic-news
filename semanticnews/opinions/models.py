from django.db import models
from openai import OpenAI
from semanticnews.users.models import User
from pgvector.django import VectorField


class Opinion(models.Model):
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    embedding = VectorField(dimensions=1536, blank=True, null=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.text[:50]

    def save(self, *args, **kwargs):
        if self.embedding is None or len(self.embedding) == 0:
            self.embedding = self.get_embedding()
        super().save(*args, **kwargs)

    def get_embedding(self):
        client = OpenAI()
        embedding = client.embeddings.create(
            input=self.text,
            model="text-embedding-3-small",
        ).data[0].embedding
        return embedding


class OpinionVote(models.Model):
    opinion = models.ForeignKey(Opinion, on_delete=models.CASCADE)
    up = models.BooleanField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.opinion} - {'up' if self.up else 'down'}"
