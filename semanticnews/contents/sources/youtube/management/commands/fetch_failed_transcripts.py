from django.core.management.base import BaseCommand
from semanticnews.contents.sources.youtube.tasks import retry_failed_transcripts


class Command(BaseCommand):
    help = "Enqueue Celery sweep to retry missing video transcripts."

    def handle(self, *args, **options):
        result = retry_failed_transcripts.delay()
        self.stdout.write(
            self.style.SUCCESS(
                f"Retry sweep dispatched (task id: {result.id})"
            )
        )
