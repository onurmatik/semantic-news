from django.contrib import admin
from .models import MCPServer


@admin.register(MCPServer)
class MCPServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'active', 'created_at', 'updated_at')
    list_filter = ('active', 'created_at', 'updated_at')
    search_fields = ('name', 'url', 'description')
    readonly_fields = ('created_at', 'updated_at')
