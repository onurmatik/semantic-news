from django.conf import settings
from slugify import slugify
from django.db import models


class Entity(models.Model):
    name = models.CharField(max_length=100)
    disambiguation = models.CharField(max_length=100, blank=True, null=True)
    slug = models.CharField(max_length=100, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.disambiguation})" if self.disambiguation else self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.__str__())
        super().save(**kwargs)

    @property
    def description(self):
        desc = self.descriptions.last()
        if desc:
            return desc.description


class Description(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='descriptions')
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.description


class EntityAlias(models.Model):
    """Alternative names for entities."""
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="aliases")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.entity.name})"

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.__str__())
        super().save(**kwargs)
