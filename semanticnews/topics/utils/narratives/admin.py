from django.contrib import admin

from .models import TopicNarrative


@admin.register(TopicNarrative)
class TopicNarrativeAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at", "short_narrative", "status")
    search_fields = ("topic__title", "narrative")
    readonly_fields = ("created_at",)

    def short_narrative(self, obj):
        return obj.narrative[:50] + ("..." if len(obj.narrative) > 50 else "")
    short_narrative.short_description = "narrative"
