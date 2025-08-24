from slugify import slugify
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from semanticnews.topics.models import Topic


class Keyword(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    topics = models.ManyToManyField(Topic, related_name='keywords', through='TopicKeyword', blank=True)

    # Variant of another more standard name
    variant_of = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE)
    variant_type = models.CharField(max_length=100, choices=(
        ('synonym', 'Synonym'),
        ('hypernym', 'Hypernym'),
        ('hyponym', 'Hyponym'),
        ('abbreviation', 'Abbreviation'),
        ('ignore', 'Ignore'),
    ), blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(**kwargs)


class TopicKeyword(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    def __str__(self):
        return f'{self.topic} - {self.keyword}'
