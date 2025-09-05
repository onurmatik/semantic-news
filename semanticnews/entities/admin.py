from django.contrib import admin
from .models import Entity, Description, EntityAlias


@admin.register(Entity)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name", "disambiguation", "slug", "created_at")
    search_fields = ("name", "disambiguation", "slug")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Description)
class DescriptionAdmin(admin.ModelAdmin):
    list_display = ("entity", "created_by", "created_at")
    search_fields = ("entity__name", "description")


@admin.register(EntityAlias)
class EntityAliasAdmin(admin.ModelAdmin):
    list_display = ("name", "entity")
    search_fields = ("name", "entity__name")
