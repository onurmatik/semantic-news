from django.contrib import admin
from .models import Keyword, TopicKeyword


class TopicKeywordInline(admin.TabularInline):
    model = TopicKeyword
    extra = 0
    fields = ("topic", "relevance", "created_by", "created_at")
    raw_id_fields = ("topic", "created_by")
    readonly_fields = ("created_at",)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "variant_of", "variant_type", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("variant_type",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}  # harmless even with your save() fallback
    inlines = [TopicKeywordInline]


@admin.register(TopicKeyword)
class TopicKeywordAdmin(admin.ModelAdmin):
    list_display = ("topic", "keyword", "relevance", "created_by", "created_at")
    search_fields = ("topic__name", "keyword__name")
    list_filter = ("created_at",)
    raw_id_fields = ("topic", "keyword", "created_by")
    readonly_fields = ("created_at",)
