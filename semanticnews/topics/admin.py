from asgiref.sync import async_to_sync
from django.contrib import admin
from .models import Topic, Keyword, TopicContent


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'event_date', 'created_at', 'updated_at')
    list_editable = ('status',)
    list_filter = ('status',)
    search_fields = ('name',)
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
    list_display = ('topic', 'added_by', 'added_at', 'get_relevance')
    list_filter = ('added_by',)
    search_fields = ('topic__name', 'added_by__username')


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'name_en', 'ignore', 'created_at', 'updated_at']
    list_filter = [
        ('name_en', admin.EmptyFieldListFilter),
        'ignore'
    ]
    list_editable = ['name_en', 'ignore']
    search_fields = ['name', 'name_en', 'slug']
    autocomplete_fields = ['variant_of']
