from django.core.management.base import BaseCommand, CommandError
from semanticnews.agenda.models import Event


class Command(BaseCommand):
    """Suggest and create the most significant agenda event(s) for a month."""

    help = "Use the agenda suggestion API to propose and create significant events for a given month."

    def add_arguments(self, parser):
        parser.add_argument(
            "year",
            type=int,
            nargs="?",
            help="Target year (e.g. 2024)",
        )
        parser.add_argument(
            "month",
            type=int,
            nargs="?",
            help="Target month as a number between 1 and 12",
        )
        parser.add_argument("--locality", default=None, help="Optional locality context")
        parser.add_argument("--categories", default=None, help="Optional comma separated categories")
        parser.add_argument("--limit", type=int, default=1, help="Maximum number of events to suggest")
        parser.add_argument(
            "--min-significance",
            type=int,
            default=1,
            dest="min_significance",
            help="Ignore suggestions rated below this value (1=very low, 5=very high)",
        )
        parser.add_argument(
            "--start-date",
            type=self._parse_date,
            dest="start_date",
            help="Optional ISO start date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            type=self._parse_date,
            dest="end_date",
            help="Optional ISO end date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--lookback-hours",
            type=int,
            dest="lookback_hours",
            help="Optional rolling window size in hours",
        )

    @staticmethod
    def _parse_date(value):
        from datetime import date

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc

    def handle(self, *args, **options):
        year = options.get("year")
        month = options.get("month")
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        lookback_hours = options.get("lookback_hours")

        using_month = year is not None or month is not None
        using_custom = any(value is not None for value in (start_date, end_date, lookback_hours))

        if using_month and using_custom:
            raise CommandError("Provide either year/month or custom date options, not both.")

        if using_month:
            if year is None or month is None:
                raise CommandError("Both year and month must be supplied together.")
        elif not using_custom:
            raise CommandError(
                "Provide a window: year/month, start/end dates, or lookback parameters."
            )

        try:
            events = Event.objects.find_major_events(
                year=year,
                month=month,
                start_date=start_date,
                end_date=end_date,
                lookback_hours=lookback_hours,
                locality=options.get("locality"),
                categories=options.get("categories"),
                limit=options.get("limit", 1),
                min_significance=options.get("min_significance", 1),
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
