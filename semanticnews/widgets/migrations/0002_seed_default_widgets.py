from django.db import migrations

from semanticnews.widgets.defaults import DEFAULT_WIDGETS


def seed_widgets(apps, schema_editor):
    Widget = apps.get_model("widgets", "Widget")
    for definition in DEFAULT_WIDGETS:
        Widget.objects.update_or_create(
            name=definition["name"],
            defaults={
                "type": definition["type"],
                "prompt": definition["prompt"],
                "response_format": definition["response_format"],
                "tools": definition["tools"],
                "template": definition["template"],
            },
        )


def unseed_widgets(apps, schema_editor):
    Widget = apps.get_model("widgets", "Widget")
    Widget.objects.filter(name__in=[definition["name"] for definition in DEFAULT_WIDGETS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("widgets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_widgets, reverse_code=unseed_widgets),
    ]
