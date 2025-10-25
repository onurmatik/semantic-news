from django.apps import AppConfig


class TopicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.topics'

    def ready(self):
        # Ensure submodule models are imported so Django sees them for migrations.
        # from semanticnews.widgets.recaps import models  # noqa: F401
        from semanticnews.widgets.images import models  # noqa: F401
        from semanticnews.widgets.arguments import models  # noqa: F401
        from semanticnews.widgets.webcontent import models  # noqa: F401
        from semanticnews.widgets.timeline import models  # noqa: F401
        from . import signals  # noqa: F401
