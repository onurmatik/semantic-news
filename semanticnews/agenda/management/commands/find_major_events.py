from django.core.management.base import BaseCommand, CommandError
from semanticnews.agenda.models import Event


class Command(BaseCommand):
    """Suggest and create the most significant agenda event(s) for a single date."""

    help = "Use the agenda suggestion API to propose and create significant events for a given date."

    def add_arguments(self, parser):
        parser.add_argument("date", type=self._parse_date, help="Target date (YYYY-MM-DD)")
        parser.add_argument("--locality", default=None, help="Optional locality context")
        parser.add_argument("--categories", default=None, help="Optional comma separated categories")
        parser.add_argument("--limit", type=int, default=1, help="Maximum number of events to suggest")
        parser.add_argument(
            "--min-significance",
            type=int,
            default=4,
            dest="min_significance",
            help="Ignore suggestions rated below this value (1=very low, 5=very high)",
        )

    @staticmethod
    def _parse_date(value):
        from datetime import date

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc

    def handle(self, *args, **options):
        try:
            events = Event.objects.find_major_events(
                options.get("date"),
                locality=options.get("locality"),
                categories=options.get("categories"),
                limit=options.get("limit", 1),
                min_significance=options.get("min_significance", 4),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Unable to fetch or create events: {exc}") from exc

        if not events:
            self.stdout.write(self.style.WARNING("No suggested events were created."))
            return

        self.stdout.write(self.style.SUCCESS(f"Created/Found {len(events)} event(s):"))
        for ev in events:
            self.stdout.write(f"- {ev.date}: {ev.title} ({ev.get_absolute_url()})")
