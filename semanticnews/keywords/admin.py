from django.contrib import admin
from .models import Keyword


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "variant_of", "variant_type", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("variant_type",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
