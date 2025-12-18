from django.contrib import admin

from .models import Reference, TopicReference


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "meta_title",
        "domain",
        "fetch_status",
        "last_fetched_at",
    )
    search_fields = ("meta_title", "url", "domain")
    list_filter = ("fetch_status", "domain")


@admin.register(TopicReference)
class TopicReferenceAdmin(admin.ModelAdmin):
    list_display = ("reference", "topic", "added_by", "added_at", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = (
        "reference__meta_title",
        "reference__url",
        "topic__titles__title",
        "topic__slug",
    )
