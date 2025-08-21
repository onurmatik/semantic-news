from django.contrib import admin
from .models import MCPServer


@admin.register(MCPServer)
class MCPServerAdmin(admin.ModelAdmin):
    list_display = ('label', 'url', 'active', 'created', 'updated')
    list_filter = ('active', 'created', 'updated')
    search_fields = ('label', 'url', 'description')
    readonly_fields = ('created', 'updated')

    fieldsets = (
        (None, {
            'fields': ('label', 'url', 'description', 'active'),
        }),
        ('Headers Configuration', {
            'fields': ('headers',),
            'description': 'Define any custom headers (e.g., api_key) as a JSON object.',
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
        }),
    )
