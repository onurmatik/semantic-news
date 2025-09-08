from django.conf import settings


def branding(request):
    """Expose site branding settings to templates."""
    return {
        "SITE_TITLE": settings.SITE_TITLE,
        "SITE_LOGO": settings.SITE_LOGO,
    }

