from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, TopicContent, TopicEntity
from .publishing.models import (
    TopicPublication,
    TopicPublicationModule,
    TopicPublishedData,
    TopicPublishedDataInsight,
    TopicPublishedDataVisualization,
    TopicPublishedDocument,
    TopicPublishedEvent,
    TopicPublishedImage,
    TopicPublishedRecap,
    TopicPublishedRelation,
    TopicPublishedText,
    TopicPublishedTweet,
    TopicPublishedWebpage,
    TopicPublishedYoutubeVideo,
)
from .utils.recaps import admin as recaps_admin  # noqa: F401
from .utils.text import admin as text_admin  # noqa: F401
from .utils.relations import admin as relations_admin  # noqa: F401
from .utils.documents import admin as documents_admin  # noqa: F401
from .utils.timeline import admin as timeline_admin  # noqa: F401


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


@admin.register(TopicPublishedText)
class TopicPublishedTextAdmin(admin.ModelAdmin):
    list_display = ("publication", "original_id", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedImage)
class TopicPublishedImageAdmin(admin.ModelAdmin):
    list_display = ("publication", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedRecap)
class TopicPublishedRecapAdmin(admin.ModelAdmin):
    list_display = ("publication", "original_id", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedRelation)
class TopicPublishedRelationAdmin(admin.ModelAdmin):
    list_display = ("publication", "original_id", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedDocument)
class TopicPublishedDocumentAdmin(admin.ModelAdmin):
    list_display = ("publication", "title", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedWebpage)
class TopicPublishedWebpageAdmin(admin.ModelAdmin):
    list_display = ("publication", "title", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedYoutubeVideo)
class TopicPublishedYoutubeVideoAdmin(admin.ModelAdmin):
    list_display = ("publication", "title", "published_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedTweet)
class TopicPublishedTweetAdmin(admin.ModelAdmin):
    list_display = ("publication", "tweet_id", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedData)
class TopicPublishedDataAdmin(admin.ModelAdmin):
    list_display = ("publication", "name", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedDataInsight)
class TopicPublishedDataInsightAdmin(admin.ModelAdmin):
    list_display = ("publication", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedDataVisualization)
class TopicPublishedDataVisualizationAdmin(admin.ModelAdmin):
    list_display = ("publication", "chart_type", "created_at")
    raw_id_fields = ("publication",)


@admin.register(TopicPublishedEvent)
class TopicPublishedEventAdmin(admin.ModelAdmin):
    list_display = ("publication", "event_id", "role", "created_at")
    raw_id_fields = ("publication",)
