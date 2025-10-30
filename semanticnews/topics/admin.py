from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, TopicContent, TopicEntity
from .publishing.models import (
    TopicPublication,
    TopicPublicationModule,
    TopicPublicationSnapshot
)
from ..widgets.recaps import admin as recaps_admin  # noqa: F401
from ..widgets.text import admin as text_admin  # noqa: F401
from ..widgets.relations import admin as relations_admin  # noqa: F401
from ..widgets.documents import admin as documents_admin  # noqa: F401
from ..widgets.timeline import admin as timeline_admin  # noqa: F401


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at', 'updated_at')
    list_editable = ('status',)
    list_filter = ('status',)
    search_fields = ('title',)
    actions = [
        'update_recap',
        'extract_entity_graph',
    ]
    readonly_fields = ('uuid', 'created_at', 'updated_at')

    def update_recap(self, request, queryset):
        for topic in queryset:
            async_to_sync(topic.update_recap)()
            self.message_user(request, f"Updated recap for '{topic}'")

    def extract_entity_graph(self, request, queryset):
        for topic in queryset:
            # Run the asynchronous method in a synchronous context
            async_to_sync(topic.extract_entity_graph)()
            # Display the result to the admin user
            self.message_user(request, f"Extracted entity graph for '{topic}'")


@admin.register(TopicContent)
class TopicContentAdmin(admin.ModelAdmin):
    list_display = ('topic', 'created_by', 'created_at', 'relevance')
    list_filter = ('created_by',)
    search_fields = ('topic__title', 'created_by__username')


@admin.register(TopicEntity)
class TopicEntityAdmin(admin.ModelAdmin):
    list_display = ("topic", "entity", "relevance", "created_by", "created_at")
    search_fields = ("topic__title", "entity__name")
    list_filter = ("created_at",)
    raw_id_fields = ("topic", "entity", "created_by")
    readonly_fields = ("created_at",)


@admin.register(TopicPublication)
class TopicPublicationAdmin(admin.ModelAdmin):
    list_display = ("topic", "published_at", "published_by")
    list_filter = ("published_at",)
    search_fields = ("topic__title", "published_by__username")
    raw_id_fields = ("topic", "published_by")


@admin.register(TopicPublicationModule)
class TopicPublicationModuleAdmin(admin.ModelAdmin):
    list_display = ("publication", "module_key", "placement", "display_order")
    list_filter = ("module_key", "placement")
    raw_id_fields = ("publication",)


@admin.register(TopicPublicationSnapshot)
class TopicPublicationSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "publication",
        "component_type",
        "module_key",
        "object_id",
        "created_at",
    )
    list_filter = ("component_type",)
    search_fields = ("publication__topic__title", "component_type", "module_key")
