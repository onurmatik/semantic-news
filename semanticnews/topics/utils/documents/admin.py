"""Admin configuration for topic document and webpage links."""

from django.contrib import admin

from .models import TopicDocumentLink, TopicWebpageLink


@admin.register(TopicDocumentLink)
class TopicDocumentLinkAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'topic',
        'document_type',
        'domain',
        'created_by',
        'created_at',
    )
    list_filter = ('document_type', 'created_at')
    search_fields = ('title', 'topic__title', 'url')
    readonly_fields = ('created_at',)
    raw_id_fields = ('topic', 'created_by')


@admin.register(TopicWebpageLink)
class TopicWebpageLinkAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'topic',
        'domain',
        'created_by',
        'created_at',
    )
    list_filter = ('created_at',)
    search_fields = ('title', 'topic__title', 'url')
    readonly_fields = ('created_at',)
    raw_id_fields = ('topic', 'created_by')
