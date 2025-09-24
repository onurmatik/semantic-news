from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from slugify import slugify

from .models import Event, Locality, Category, Source, Description
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
        "locality",
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
        "locality",
        ("categories", admin.RelatedOnlyFieldListFilter),
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

    actions = ("update_embeddings", "publish_events")
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

    @admin.action(description="Publish selected events")
    def publish_events(self, request, queryset):
        updated = queryset.exclude(status="published").update(status="published")
        self.message_user(request, f"Published {updated} event(s).", messages.SUCCESS)

    def _redirect_back(self, request):
        base = reverse("admin:agenda_event_changelist")
        qs = request.META.get("QUERY_STRING", "")
        return HttpResponseRedirect(f"{base}?{qs}" if qs else base)

    def _resolve_year_month(self, request):
        try:
            year = int(request.GET.get("date__year") or 0)
            month = int(request.GET.get("date__month") or 0)
        except ValueError:
            return None, None
        return (year, month) if (year > 0 and 1 <= month <= 12) else (None, None)

    # Custom URLs
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("suggest/", self.admin_site.admin_view(self.suggest_view), name="agenda_event_suggest"),
            path("find-major/", self.admin_site.admin_view(self.find_major_view), name="agenda_event_find_major"),
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

    def find_major_view(self, request):
        if not self.has_change_permission(request):
            messages.error(request, "You don't have permission to do that.")
            return self._redirect_back(request)

        year, month = self._resolve_year_month(request)
        if not (year and month):
            messages.error(request, "Select a month first (use the Date filter or date hierarchy).")
            return self._redirect_back(request)

        # pass through current locality / single category filters if present
        locality_name = None
        loc_id = request.GET.get("locality__id__exact")
        if loc_id:
            loc = Locality.objects.filter(pk=loc_id).first()
            locality_name = loc.name if loc else None

        categories = None
        cat_id = request.GET.get("categories__id__exact")
        if cat_id:
            cat = Category.objects.filter(pk=cat_id).first()
            categories = cat.name if cat else None

        try:
            limit = int(request.GET.get("limit", "1"))
        except ValueError:
            limit = 1

        try:
            events = Event.objects.find_major_events(
                year=year,
                month=month,
                locality=locality_name,
                categories=categories,
                limit=limit,
            )
        except Exception as exc:
            messages.error(request, f"Couldn't fetch/create events: {exc}")
            return self._redirect_back(request)

        if events:
            messages.success(request, f"Created/Found {len(events)} event(s) for {year}-{month:02d}.")
        else:
            messages.warning(request, f"No suggestions created for {year}-{month:02d}.")
        return self._redirect_back(request)


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
    list_display = ['url', 'domain']
    search_fields = ['url', 'domain']
    readonly_fields = ['domain']


@admin.register(Description)
class DescriptionAdmin(admin.ModelAdmin):
    list_display = ['event', 'created_by', 'created_at']
    search_fields = ['event__title', 'description']
