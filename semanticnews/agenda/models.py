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
        year: int,
        month: int,
        *,
        locality: str | None = None,
        categories: str | None = None,
        limit: int = 1,
        distance_threshold: float = 0.15,
    ) -> list["Event"]:
        from semanticnews.agenda.api import suggest_events, AgendaEventResponse
        import calendar
        from datetime import date
        from django.db import transaction

        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")

        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

        locality_code = resolve_locality_code(locality)
        locality_label = get_locality_label(locality_code) if locality_code else None

        # Build exclude list from existing events in that month
        existing_qs = (
            self.filter(date__year=year, date__month=month)
            .prefetch_related("categories", "sources")
            .order_by("date")
        )
        exclude = [
            AgendaEventResponse(
                title=e.title,
                date=e.date,
                categories=[c.name for c in e.categories.all()],
                sources=[s.url for s in e.sources.all()],
            )
            for e in existing_qs
        ] or None

        suggestions = suggest_events(
            start_date=start_date,
            end_date=end_date,
            locality=locality_label,
            categories=categories,
            limit=limit,
            exclude=exclude,
        )

        created_events: list[Event] = []
        if not suggestions:
            return created_events

        # Reuse one OpenAI client for all suggestions
        client = OpenAI()

        for suggestion in suggestions:
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
                    },
                    distance_threshold=distance_threshold,
                )

                # If matched existing and it lacks locality, attach it (don’t override if set)
                if not created and locality_code and not event.locality:
                    event.locality = locality_code
                    event.save(update_fields=["locality"])

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
            client = OpenAI()
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
