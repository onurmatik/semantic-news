from datetime import date
import calendar

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, render
from pgvector.django import L2Distance

from .models import Event, Locality


DISTANCE_THRESHOLD = 1


def event_detail(request, year, month, day, slug):
    obj = get_object_or_404(
        Event.objects.prefetch_related("topics"),
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
        )
        similar_events = list(similar_qs)
        exclude_events = [
            {"title": ev.title, "date": ev.date.isoformat()} for ev in similar_events
        ]
    else:
        similar_events = Event.objects.none()
        exclude_events = []

    localities = Locality.objects.all().order_by("-is_default", "name")

    return render(
        request,
        "agenda/event_detail.html",
        {
            "event": obj,
            "similar_events": similar_events,
            "exclude_events": exclude_events,
            "localities": localities,
        },
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
    elif month is not None:
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        period = {"granularity": "month", "year": year, "month": month}
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        period = {"granularity": "year", "year": year}

    qs = (
        Event.objects.filter(date__range=(start, end))
        .select_related("created_by")
        .prefetch_related("contents")
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

    context = {
        "events": events,
        "period": period,   # helpful for headings/breadcrumbs
        "start": start,
        "end": end,
    }
    return render(request, "agenda/event_list.html", context)
