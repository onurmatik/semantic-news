from django.apps import AppConfig


class TopicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.topics'

    def ready(self):
        # Ensure submodule models are imported so Django sees them for migrations.
        from .tools.recaps import models  # noqa: F401
        from .tools.images import models  # noqa: F401
        from .tools.arguments import models  # noqa: F401
