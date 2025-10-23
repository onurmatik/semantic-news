from django.contrib import admin

from .models import TopicRecap


@admin.register(TopicRecap)
class TopicRecapAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at", "short_recap", "status")
    search_fields = ("topic__title", "recap")
    readonly_fields = ("created_at",)

    def short_recap(self, obj):
        return obj.recap[:50] + ("..." if len(obj.recap) > 50 else "")
    short_recap.short_description = "recap"
