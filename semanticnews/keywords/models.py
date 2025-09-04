from slugify import slugify
from django.db import models


class Keyword(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
