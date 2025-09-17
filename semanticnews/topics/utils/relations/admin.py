from django.contrib import admin

from .models import TopicEntityRelation


@admin.register(TopicEntityRelation)
class TopicEntityRelationAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at", "short_relations", "status")
    search_fields = ("topic__title",)
    readonly_fields = ("created_at",)

    def short_relations(self, obj):
        data = str(obj.relations)
        return data[:50] + ("..." if len(data) > 50 else "")
    short_relations.short_description = "relations"
