from datetime import date
import calendar

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, render
from pgvector.django import L2Distance

from .models import Event


def event_detail(request, year, month, day, slug):
    obj = get_object_or_404(
        Event, slug=slug, date__year=year, date__month=month, date__day=day
    )

    if obj.embedding is not None:
        similar_events = (
            Event.objects.exclude(id=obj.id)
            .exclude(embedding__isnull=True)
            .order_by(L2Distance("embedding", obj.embedding))[:5]
        )
    else:
        similar_events = Event.objects.none()

    return render(
        request,
        "agenda/event_detail.html",
        {
            "event": obj,
            "similar_events": similar_events,
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
