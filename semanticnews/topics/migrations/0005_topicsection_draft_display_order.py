from django.db import migrations, models


def copy_display_order_to_draft(apps, schema_editor):
    TopicSection = apps.get_model("topics", "TopicSection")
    TopicSection.objects.all().update(draft_display_order=models.F("display_order"))


def revert_draft_order(apps, schema_editor):
    TopicSection = apps.get_model("topics", "TopicSection")
    TopicSection.objects.all().update(display_order=models.F("draft_display_order"))


class Migration(migrations.Migration):
    dependencies = [
        ("topics", "0004_topicsection_is_draft_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicsection",
            name="draft_display_order",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(copy_display_order_to_draft, revert_draft_order),
    ]
