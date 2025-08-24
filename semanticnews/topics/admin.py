from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, TopicContent


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
