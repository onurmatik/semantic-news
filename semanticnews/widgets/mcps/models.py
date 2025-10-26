from django.db import models


class MCPServer(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=100, blank=True)
    url = models.URLField()

    headers = models.JSONField(default=dict, blank=True)

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'widgets'

    def __str__(self):
        return self.name
