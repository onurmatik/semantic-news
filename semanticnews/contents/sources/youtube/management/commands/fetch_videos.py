from django.core.management.base import BaseCommand
from semanticnews.contents.sources.youtube.models import Channel
from semanticnews.contents.sources.youtube.tasks import fetch_channel_content


class Command(BaseCommand):
    help = "Fetches the latest videos and stats for all channels"

    def handle(self, *args, **options):
        """
        Enqueue a Celery task for each active channel to fetch its latest videos and stats.
        """
        channels = Channel.objects.filter(active=True)
        for channel in channels:
            fetch_channel_content.delay(channel.pk)
            self.stdout.write(self.style.SUCCESS(
                f"Enqueued fetch for channel {channel.pk}"
            ))
