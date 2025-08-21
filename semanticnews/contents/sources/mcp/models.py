from django.db import models


class MCPServer(models.Model):
    label = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    description = models.CharField(max_length=100, blank=True)
    headers = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.label
