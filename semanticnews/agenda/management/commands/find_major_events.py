from django.core.management.base import BaseCommand, CommandError
from semanticnews.agenda.models import Event


class Command(BaseCommand):
    """Suggest and create the most significant agenda event(s) for a month."""

    help = "Use the agenda suggestion API to propose and create significant events for a given month."

    def add_arguments(self, parser):
        parser.add_argument("year", type=int, help="Target year (e.g. 2024)")
        parser.add_argument("month", type=int, help="Target month as a number between 1 and 12")
        parser.add_argument("--locality", default=None, help="Optional locality context")
        parser.add_argument("--categories", default=None, help="Optional comma separated categories")
        parser.add_argument("--limit", type=int, default=1, help="Maximum number of events to suggest")

    def handle(self, *args, **options):
        try:
            events = Event.objects.find_major_events(
                year=options["year"],
                month=options["month"],
                locality=options.get("locality"),
                categories=options.get("categories"),
                limit=options.get("limit", 1),
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
