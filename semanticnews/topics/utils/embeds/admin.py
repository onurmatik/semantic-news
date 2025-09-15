from django.contrib import admin

from .models import TopicSocialEmbed


@admin.register(TopicSocialEmbed)
class TopicSocialEmbedAdmin(admin.ModelAdmin):
    list_display = ('topic', 'provider', 'url', 'created_at')
    search_fields = ('url',)
