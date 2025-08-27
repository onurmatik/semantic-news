from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.safestring import mark_safe
from slugify import slugify

from .models import Event, Locality, Category, Source
from .forms import EventSuggestForm
from .api import suggest_events, AgendaEventResponse


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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    # Columns
    list_display = (
        "title",
        "slug",
        "date",
        "status",
        "has_embedding_flag",
    )
    list_editable = ("slug", "status",)
    list_display_links = ("title",)

    # Filters & search
    list_filter = (
        HasContentsFilter,
        HasEmbeddingFilter,
        "status",
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

    actions = ("update_embeddings",)
    change_list_template = "admin/agenda/event/change_list.html"

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

    def update_embeddings(self, request, queryset):
        updated = 0
        for event in queryset:
            event.embedding = event.get_embedding()
            event.save(update_fields=["embedding"])
            updated += 1
        self.message_user(request, f"Updated embeddings for {updated} event(s).", messages.SUCCESS)

    # Custom URLs
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("suggest/", self.admin_site.admin_view(self.suggest_view), name="agenda_event_suggest"),
        ]
        return my_urls + urls

    def suggest_view(self, request):
        form = EventSuggestForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            start = form.cleaned_data["start_date"]
            end = form.cleaned_data["end_date"]
            locality = form.cleaned_data.get("locality")
            selected_categories = form.cleaned_data.get("categories")

            existing = Event.objects.filter(date__range=(start, end)).values("title", "date")
            exclude = [AgendaEventResponse(title=e["title"], date=e["date"]) for e in existing]

            suggestions = suggest_events(
                start_date=start,
                end_date=end,
                locality=locality.name if locality else None,
                categories=", ".join(c.name for c in selected_categories) if selected_categories else None,
                exclude=exclude,
            )

            print(suggestions.event_list)

            created = 0
            for item in suggestions.event_list:
                event = Event.objects.create(
                    title=item.title,
                    date=item.date,
                    locality=locality,
                    created_by=request.user if request.user.is_authenticated else None,
                )
                for url in item.sources:
                    source_obj, _ = Source.objects.get_or_create(url=url)
                    event.sources.add(source_obj)
                for cat_name in item.categories:
                    category, _ = Category.objects.get_or_create(name=cat_name)
                    event.categories.add(category)
                created += 1

            messages.success(request, f"Created {created} new events from suggestions.")
            return redirect("admin:agenda_event_changelist")

        context = {
            "form": form,
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
        }
        return render(request, "admin/agenda/event/suggest.html", context)


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['url']
    search_fields = ['url']
