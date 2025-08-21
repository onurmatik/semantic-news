from django.contrib import admin
from .models import VectorStore, VectorStoreFile


@admin.register(VectorStore)
class VectorStoreAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'created_at',
        'created',
    )
    list_filter = ('created_at',)
    search_fields = ('name', 'name_en', 'vs_id')
    readonly_fields = ('uuid', 'created_at', 'vs_id')

    def created(self, obj):
        return bool(obj.vs_id)
    created.boolean = True


@admin.register(VectorStoreFile)
class VectorStoreFileAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'lang',
        'created_at',
        'uploaded',
    )
    list_filter = ('lang', 'created_at')
    search_fields = ('name', 'name_en', 'file_id')
    readonly_fields = ('uuid', 'created_at', 'file_id')

    def uploaded(self, obj):
        return bool(obj.file_id)
    uploaded.boolean = True
