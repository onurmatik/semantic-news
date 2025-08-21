# contents/admin.py
from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Source, Content


# ---- Custom list filters -----------------------------------------------------

class HasURLFilter(admin.SimpleListFilter):
    title = "has URL"
    parameter_name = "has_url"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(url__isnull=True).exclude(url__exact="")
        if self.value() == "no":
            return queryset.filter(Q(url__isnull=True) | Q(url__exact=""))
        return queryset


class HasEmbeddingFilter(admin.SimpleListFilter):
    title = "has embedding"
    parameter_name = "has_embedding"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(embedding__isnull=True)
        if self.value() == "no":
            return queryset.filter(embedding__isnull=True)
        return queryset


# ---- Inlines -----------------------------------------------------------------

class ContentInline(admin.TabularInline):
    model = Content
    fields = ("uuid", "title", "content_type", "language_code", "published_at")
    readonly_fields = ("uuid", "title", "content_type", "language_code", "published_at")
    extra = 0
    show_change_link = True
    can_delete = False


# ---- Source admin ------------------------------------------------------------

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "is_active", "content_count")
    list_filter = ("is_active",)
    search_fields = ("name", "domain")
    ordering = ("name",)
    inlines = [ContentInline]
    actions = ("make_active", "make_inactive")

    @admin.display(ordering="content_count", description="Contents")
    def content_count(self, obj):
        # annotated in get_queryset for ordering efficiency
        return obj.content_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(content_count=Count("contents"))

    @admin.action(description="Mark selected sources as active")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} source(s) marked active.")

    @admin.action(description="Mark selected sources as inactive")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} source(s) marked inactive.")


# ---- Content admin -----------------------------------------------------------

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    # Columns
    list_display = (
        "short_title",
        "content_type",
        "source_link",
        "language_code",
        "published_at",
        "created_at",
        "url_link",
        "has_embedding_flag",
    )
    list_display_links = ("short_title",)

    # Filters & search
    list_filter = (
        "content_type",
        "language_code",
        "source",
        HasURLFilter,
        HasEmbeddingFilter,
        ("published_at", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "uuid",
        "title",
        "url",
        "content_type",
        "language_code",
        "source__name",
        "source__domain",
        "created_by__username",
        "created_by__email",
    )

    # Performance & relations
    list_select_related = ("source", "created_by")
    autocomplete_fields = ("source", "created_by")  # ensure related admins provide search_fields

    # Meta
    ordering = ("-published_at", "-created_at")
    date_hierarchy = "published_at"
    readonly_fields = ("uuid", "created_at", "embedding_pretty")
    fieldsets = (
        ("Identity & linkage", {
            "fields": ("uuid", "source", "url", "content_type", "language_code", "created_by")
        }),
        ("Content", {
            "fields": ("title", "markdown")
        }),
        ("Timestamps", {
            "fields": ("published_at", "created_at")
        }),
        ("Metadata", {
            "fields": ("metadata", "embedding_pretty"),
            "description": "Raw JSON is editable. Embedding is shown read-only."
        }),
        # keep the actual VectorField out of the form to avoid accidental edits
    )
    # Hide the raw vector field from form, but keep it on the model
    exclude = ("embedding",)

    # ---- Column helpers ----

    @admin.display(description="Title")
    def short_title(self, obj):
        if obj.title:
            return (obj.title[:90] + "…") if len(obj.title) > 90 else obj.title
        return "(untitled)"

    @admin.display(description="Source", ordering="source__name")
    def source_link(self, obj):
        if not obj.source:
            return "-"
        return format_html(
            '<a href="{}">{}</a>',
            f"../source/{obj.source.pk}/change/",
            obj.source.name,
        )

    @admin.display(description="URL")
    def url_link(self, obj):
        if not obj.url:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">open</a>', obj.url)

    @admin.display(boolean=True, description="Embedding")
    def has_embedding_flag(self, obj):
        return obj.embedding is not None

    @admin.display(description="Embedding (preview)")
    def embedding_pretty(self, obj):
        if obj.embedding is None:
            return "-"
        # Show only first 16 dims to keep page tidy
        try:
            first = ", ".join(str(x) for x in obj.embedding[:16])
        except Exception:
            first = "(unavailable)"
        return mark_safe(f"<code>[{first}{' …' if len(obj.embedding or []) > 16 else ''}]</code>")
