from datetime import date, timedelta
import calendar

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.db.models import Prefetch
from pgvector.django import L2Distance

from .models import Event, Locality, Category
from semanticnews.topics.models import Topic


DISTANCE_THRESHOLD = 1


def event_detail(request, year, month, day, slug):
    obj = get_object_or_404(
        Event.objects.prefetch_related(
            Prefetch("topics", queryset=Topic.objects.filter(status="published"))
        ),
        slug=slug,
        date__year=year,
        date__month=month,
        date__day=day,
    )

    if obj.embedding is not None:
        similar_qs = (
            Event.objects.exclude(id=obj.id)
            .exclude(embedding__isnull=True)
            .annotate(distance=L2Distance("embedding", obj.embedding))
            .filter(distance__lt=DISTANCE_THRESHOLD)
            .order_by("distance")[:50]
            .prefetch_related("categories")
        )
        similar_events = list(similar_qs)
        exclude_events = [
            {"title": ev.title, "date": ev.date.isoformat()} for ev in similar_events
        ]
    else:
        similar_events = Event.objects.none()
        exclude_events = []

    categories = (
        Category.objects.filter(event__in=similar_events)
        .order_by("name")
        .distinct()
    )

    localities = Locality.objects.all().order_by("-is_default", "name")

    context = {
        "event": obj,
        "topics": obj.topics.all(),
        "similar_events": similar_events,
        "exclude_events": exclude_events,
        "localities": localities,
        "categories": categories,
    }
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user)
    return render(
        request,
        "agenda/event_detail.html",
        context,
    )


def event_list(request, year, month=None, day=None):
    """
    Lists events for a given year, month, or day, based on which
    URL pattern matched:
      - /<year>/
      - /<year>/<month>/
      - /<year>/<month>/<day>/
    """
    year = int(year)
    if month is not None:
        month = int(month)
    if day is not None:
        day = int(day)

    # Determine the date range [start, end]
    if day is not None:
        start = end = date(year, month, day)
        period = {"granularity": "day", "year": year, "month": month, "day": day}
        prev_date = start - timedelta(days=1)
        next_date = start + timedelta(days=1)
        prev_url = reverse(
            "event_list_day",
            kwargs={
                "year": f"{prev_date.year:04}",
                "month": f"{prev_date.month:02}",
                "day": f"{prev_date.day:02}",
            },
        )
        next_url = reverse(
            "event_list_day",
            kwargs={
                "year": f"{next_date.year:04}",
                "month": f"{next_date.month:02}",
                "day": f"{next_date.day:02}",
            },
        )
    elif month is not None:
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        period = {"granularity": "month", "year": year, "month": month}
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        prev_url = reverse(
            "event_list_month",
            kwargs={"year": f"{prev_year:04}", "month": f"{prev_month:02}"},
        )
        next_url = reverse(
            "event_list_month",
            kwargs={"year": f"{next_year:04}", "month": f"{next_month:02}"},
        )
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        period = {"granularity": "year", "year": year}
        prev_url = reverse("event_list_year", kwargs={"year": f"{year - 1:04}"})
        next_url = reverse("event_list_year", kwargs={"year": f"{year + 1:04}"})

    qs = (
        Event.objects.filter(date__range=(start, end))
        .select_related("created_by")
        .prefetch_related("contents", "categories")
        .order_by("date", "slug")  # stable order within the period
    )

    # Pagination (optional): ?page=2
    paginator = Paginator(qs, 20)  # 20 per page; tweak as needed
    page = request.GET.get("page")
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        events = paginator.page(1)
    except EmptyPage:
        events = paginator.page(paginator.num_pages)

    exclude_events = [
        {"title": ev.title, "date": ev.date.isoformat()} for ev in qs
    ]

    categories = (
        Category.objects.filter(event__in=events.object_list)
        .order_by("name")
        .distinct()
    )

    localities = Locality.objects.all().order_by("-is_default", "name")

    context = {
        "events": events,
        "period": period,   # helpful for headings/breadcrumbs
        "start": start,
        "end": end,
        "exclude_events": exclude_events,
        "localities": localities,
        "categories": categories,
        "prev_url": prev_url,
        "next_url": next_url,
    }
    if request.user.is_authenticated:
        context["user_topics"] = Topic.objects.filter(created_by=request.user)
    return render(request, "agenda/event_list.html", context)
