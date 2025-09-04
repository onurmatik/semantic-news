from django.apps import AppConfig


class ContentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.contents'

    def ready(self):
        # Ensure submodule models are imported so Django sees them for migrations.
        from .sources.rss import models  # noqa: F401
        from .sources.youtube import models  # noqa: F401
        from .sources.websearch import models  # noqa: F401
