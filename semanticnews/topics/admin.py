from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, RelatedTopic, RelatedEntity, RelatedEvent
from .recaps import admin as recaps_admin  # noqa: F401
from ..widgets.text import admin as text_admin  # noqa: F401
from ..widgets.webcontent import admin as webcontent_admin  # noqa: F401


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at', 'last_published_at')
    list_editable = ('status',)
    list_filter = ('status',)
    search_fields = ('title',)
    actions = [
        'update_recap',
        'extract_entity_graph',
    ]
    readonly_fields = ('uuid', 'created_at', 'last_published_at')

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

