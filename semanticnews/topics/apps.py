from django.apps import AppConfig


class TopicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.topics'

    def ready(self):
        # Ensure submodule models are imported so Django sees them for migrations.
        # from .utils.recaps import models  # noqa: F401
        from .utils.images import models  # noqa: F401
        from .utils.arguments import models  # noqa: F401
        from .utils.documents import models  # noqa: F401
        from .utils.timeline import models  # noqa: F401
        from . import signals  # noqa: F401
