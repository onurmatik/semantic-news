from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from slugify import slugify

from .models import Entry


class HasEmbeddingFilter(admin.SimpleListFilter):
    title = "has embedding"
    parameter_name = "has_embedding"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(embedding__isnull=True)
        if self.value() == "no":
            return queryset.filter(embedding__isnull=True)
        return queryset


class HasContentsFilter(admin.SimpleListFilter):
    title = "has contents"
    parameter_name = "has_contents"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(contents__isnull=False).distinct()
        if self.value() == "no":
            return queryset.filter(contents__isnull=True)
        return queryset


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    # Columns
    list_display = (
        "title",
        "slug",
        "date",
        "contents_count",
        "created_by",
        "created_at",
        "updated_at",
        "has_embedding_flag",
    )
    list_display_links = ("title",)

    # Filters & search
    list_filter = (
        HasContentsFilter,
        HasEmbeddingFilter,
        "created_by",
        ("date", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
        ("updated_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "uuid",
        "title",
        "slug",
        "contents__title",
        "contents__url",
        "contents__source__name",
    )
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")

    # Relations / perf
    list_select_related = ("created_by",)
    autocomplete_fields = ("created_by",)

    readonly_fields = ("uuid", "created_at", "updated_at", "embedding_pretty")
    exclude = ("embedding",)
    prepopulated_fields = {"slug": ("title",)}

    actions = ("fill_missing_slugs", "clear_embeddings")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(contents_count=Count("contents", distinct=True))

    @admin.display(ordering="contents_count", description="Contents")
    def contents_count(self, obj):
        return obj.contents_count

    @admin.display(boolean=True, description="Embedding")
    def has_embedding_flag(self, obj):
        return obj.embedding is not None

    @admin.display(description="Embedding (preview)")
    def embedding_pretty(self, obj):
        if obj.embedding is None:
            return "-"
        try:
            first = ", ".join(str(x) for x in obj.embedding[:16])
            more = " …" if len(obj.embedding or []) > 16 else ""
            return mark_safe(f"<code>[{first}{more}]</code>")
        except Exception:
            return "(unavailable)"

    # Avoid duplicate rows when searching across M2M
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset.distinct(), True

    @admin.action(description="Fill missing slugs from titles")
    def fill_missing_slugs(self, request, queryset):
        updated = 0
        for entry in queryset.filter(Q(slug__isnull=True) | Q(slug__exact="")):
            new_slug = slugify(entry.title) if entry.title else None
            if new_slug:
                entry.slug = new_slug
                entry.save(update_fields=["slug"])
                updated += 1
        self.message_user(request, f"Filled slugs for {updated} entr{ 'y' if updated == 1 else 'ies' }.")

    @admin.action(description="Clear embeddings")
    def clear_embeddings(self, request, queryset):
        updated = queryset.update(embedding=None)
        self.message_user(request, f"Cleared embeddings on {updated} entr{ 'y' if updated == 1 else 'ies' }.")
