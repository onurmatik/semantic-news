from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, TopicRecap, RelatedTopic, RelatedEntity, RelatedEvent


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at', 'last_published_at')
    list_editable = ('status',)
    list_filter = ('status',)
    search_fields = ('titles__title',)
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


@admin.register(TopicRecap)
class TopicRecapAdmin(admin.ModelAdmin):
    list_display = ("topic", "created_at", "short_recap", "status")
    search_fields = ("topic__title", "recap")
    readonly_fields = ("created_at",)

    def short_recap(self, obj):
        return obj.recap[:50] + ("..." if len(obj.recap) > 50 else "")
    short_recap.short_description = "recap"
