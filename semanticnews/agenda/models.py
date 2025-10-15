import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.db import models
from django.urls import reverse
from pgvector.django import HnswIndex, L2Distance, VectorField
from slugify import slugify

from semanticnews.agenda.localities import get_locality_label, resolve_locality_code
from semanticnews.openai import OpenAI


class EventManager(models.Manager):
    """Custom manager for :class:`Event` objects."""

    def get_or_create_semantic(
        self,
        *,
        date,
        embedding,
        defaults=None,
        distance_threshold=0.15,
    ):
        """Return an event matching ``date`` and ``embedding`` proximity.

        This behaves similarly to :meth:`django.db.models.Manager.get_or_create`
        but checks for an existing event on the given ``date`` whose embedding is
        within ``distance_threshold`` of the supplied ``embedding``. If such an
        event exists, it is returned; otherwise a new event is created using the
        provided ``defaults``.

        Args:
            date (datetime.date): The date of the candidate event.
            embedding (list[float]): Embedding vector for similarity search.
            defaults (dict | None): Fields for creating a new event when no
                similar event is found.
            distance_threshold (float): Maximum L2 distance for considering two
                events the same.

        Returns:
            tuple[Event, bool]: ``(event, created)`` where ``created`` indicates
            whether a new event was created.
        """

        defaults = defaults or {}
        qs = (
            self.get_queryset()
            .filter(date=date)
            .exclude(embedding__isnull=True)
            .annotate(distance=L2Distance("embedding", embedding))
            .order_by("distance")
        )

        match = qs.filter(distance__lt=distance_threshold).first()
        if match:
            return match, False

        params = {**defaults, "date": date, "embedding": embedding}
        obj = self.create(**params)
        return obj, True

    def find_major_events(
        self,
        year: int | None = None,
        month: int | None = None,
        *,
        start_date=None,
        end_date=None,
        lookback_hours: int | None = None,
        locality: str | None = None,
        categories: str | None = None,
        limit: int = 1,
        min_significance: int = 1,
        distance_threshold: float = 0.15,
    ) -> list["Event"]:
        from semanticnews.agenda.api import suggest_events, AgendaEventResponse
        import calendar
        from datetime import date, datetime, time, timedelta
        from django.db import transaction
        from django.utils import timezone

        window_start = None
        window_end = None

        using_month = year is not None or month is not None
        using_custom = any(value is not None for value in (start_date, end_date, lookback_hours))

        if using_month and using_custom:
            raise ValueError("Provide either year/month or custom date options, not both.")

        if using_month:
            if year is None or month is None:
                raise ValueError("Both year and month must be supplied together.")
            if month < 1 or month > 12:
                raise ValueError("Month must be between 1 and 12")

            window_start = date(year, month, 1)
            _, last_day = calendar.monthrange(year, month)
            window_end = date(year, month, last_day)
        else:
            if not using_custom:
                raise ValueError(
                    "Provide a window: year/month, start/end dates, or lookback parameters."
                )

            if lookback_hours is not None and lookback_hours <= 0:
                raise ValueError("Lookback hours must be a positive integer")

            if start_date is not None and not isinstance(start_date, date):
                raise ValueError("start_date must be a date instance")

            if end_date is not None and not isinstance(end_date, date):
                raise ValueError("end_date must be a date instance")

            window_start = start_date
            window_end = end_date

            if lookback_hours is not None:
                delta = timedelta(hours=lookback_hours)
                if window_start and window_end:
                    raise ValueError(
                        "Cannot use lookback_hours together with explicit start and end dates."
                    )

                if window_end and not window_start:
                    end_dt = datetime.combine(window_end, time.max)
                    computed_start = (end_dt - delta).date()
                    window_start = computed_start
                elif window_start and not window_end:
                    start_dt = datetime.combine(window_start, time.min)
                    computed_end = (start_dt + delta).date()
                    window_end = computed_end
                elif not window_start and not window_end:
                    end_dt = timezone.now()
                    window_end = end_dt.date()
                    computed_start = (end_dt - delta).date()
                    window_start = computed_start

            if window_start is None or window_end is None:
                raise ValueError("Both start and end dates must be provided or derivable.")

        if window_start > window_end:
            raise ValueError("Start date must be on or before end date")

        try:
            min_significance = int(min_significance)
        except (TypeError, ValueError) as exc:
            raise ValueError("min_significance must be an integer.") from exc

        if not 1 <= min_significance <= 5:
            raise ValueError("min_significance must be between 1 and 5.")

        locality_code = resolve_locality_code(locality)
        locality_label = get_locality_label(locality_code) if locality_code else None

        # Build exclude list from existing events in that month
        existing_qs = (
            self.filter(date__range=(window_start, window_end))
            .prefetch_related("categories", "sources")
            .order_by("date")
        )
        exclude = [
            AgendaEventResponse(
                title=e.title,
                date=e.date,
                categories=[c.name for c in e.categories.all()],
                sources=[s.url for s in e.sources.all()],
                significance=e.significance,
            )
            for e in existing_qs
        ] or None

        suggestions = suggest_events(
            start_date=window_start,
            end_date=window_end,
            locality=locality_label,
            categories=categories,
            limit=limit,
            exclude=exclude,
        )

        created_events: list[Event] = []
        if not suggestions:
            return created_events

        def _normalized_significance(value: int | None) -> int:
            if value is None:
                return 3
            try:
                coerced = int(value)
            except (TypeError, ValueError):
                return 3
            return max(1, min(5, coerced))

        filtered_suggestions = []
        for suggestion in suggestions:
            rating = _normalized_significance(getattr(suggestion, "significance", None))
            if rating < min_significance:
                continue
            suggestion.significance = rating
            filtered_suggestions.append(suggestion)

        if not filtered_suggestions:
            return created_events

        # Reuse one OpenAI client for all suggestions
        with OpenAI() as client:
            for suggestion in filtered_suggestions:
                with transaction.atomic():
                    embed_text = f"{suggestion.title} - {suggestion.date}\n{', '.join(suggestion.categories or [])}"
                    embedding = client.embeddings.create(
                        input=embed_text,
                        model="text-embedding-3-small",
                    ).data[0].embedding

                    # Semantic de-dup on SAME DATE using L2 distance
                    event, created = self.get_or_create_semantic(
                        date=suggestion.date,
                        embedding=embedding,
                        defaults={
                            "title": suggestion.title,
                            "confidence": None,
                            "status": "draft",
                            "locality": locality_code,
                            "significance": suggestion.significance,
                        },
                        distance_threshold=distance_threshold,
                    )

                    updated_fields: list[str] = []

                    # If matched existing and it lacks locality, attach it (don’t override if set)
                    if not created and locality_code and not event.locality:
                        event.locality = locality_code
                        updated_fields.append("locality")

                    if not created and event.significance != suggestion.significance:
                        event.significance = suggestion.significance
                        updated_fields.append("significance")

                    if updated_fields:
                        event.save(update_fields=updated_fields)

                    # Attach categories
                    for name in suggestion.categories or []:
                        cat, _ = Category.objects.get_or_create(name=name)
                        event.categories.add(cat)

                    # Attach sources
                    for url in suggestion.sources or []:
                        src, _ = Source.objects.get_or_create(url=url)
                        event.sources.add(src)

                    # Recompute embedding after M2M changes to keep it fresh
                    new_emb = event.get_embedding()
                    if new_emb is not None:
                        event.embedding = new_emb
                        event.save(update_fields=["embedding"])

                    created_events.append(event)

        return created_events


class Event(models.Model):
    objects = EventManager()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    date = models.DateField(db_index=True)

    categories = models.ManyToManyField('agenda.Category', blank=True)
    significance = models.PositiveSmallIntegerField(choices=(
        (1, 'Very low'),
        (2, 'Low'),
        (3, 'Normal'),
        (4, 'High'),
        (5, 'Very high'),
    ), default=4)
    locality = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    status = models.CharField(max_length=20, choices=(
        ('draft', 'Draft'),
        ('published', 'Published'),
    ), default='draft')

    sources = models.ManyToManyField('agenda.Source', blank=True)

    confidence = models.FloatField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.date}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['title', 'date'], name='unique_entry_title_date'),
        ]
        indexes = [
            HnswIndex(
                name='entry_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        if self.embedding is None:
            self.embedding = self.get_embedding()

        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        # Use zero-padded YYYY/MM/DD to match the requested format exactly
        return reverse(
            'event_detail',
            kwargs={
                'year': f'{self.date:%Y}',
                'month': f'{self.date:%m}',
                'day': f'{self.date:%d}',
                'slug': self.slug,
            },
        )

    def get_embedding(self):
        if self.pk is None:
            return None

        if self.embedding is None or len(self.embedding) == 0:
            with OpenAI() as client:
                text = (
                    f"{self.title} - {self.date}\n"
                    f"{', '.join([c.name for c in self.categories.all()])}"
                )
                embedding = client.embeddings.create(
                    input=text,
                    model='text-embedding-3-small'
                ).data[0].embedding
            return embedding

    @property
    def locality_label(self):
        return get_locality_label(self.locality)

    @property
    def description(self):
        desc = self.descriptions.last()
        if desc:
            return desc.description


class Description(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='descriptions')
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='event_descriptions',
        blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.description

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'categories'


class Source(models.Model):
    url = models.URLField(max_length=200)
    domain = models.CharField(max_length=200, db_index=True)

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        if not self.domain:
            self.domain = self.get_domain()
        super().save(*args, **kwargs)

    def get_domain(self):
        parsed_url = urlparse(self.url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
