from django.contrib import admin

from .models import TopicText


@admin.register(TopicText)
class TopicTextAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at", "short_preview", "status")
    search_fields = ("topic__title", "content")
    readonly_fields = ("created_at", "updated_at")

    def short_preview(self, obj):
        preview = (obj.content or "")[:50]
        if obj.content and len(obj.content) > 50:
            preview += "..."
        return preview

    short_preview.short_description = "content"
