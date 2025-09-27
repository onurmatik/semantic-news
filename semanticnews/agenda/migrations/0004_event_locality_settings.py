from django.db import migrations, models


def copy_locality_forward(apps, schema_editor):
    Event = apps.get_model("agenda", "Event")

    for event in Event.objects.select_related("locality").all():
        if event.locality_id:
            event.locality_name = event.locality.name
            event.save(update_fields=["locality_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0003_alter_source_domain"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="locality_name",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(copy_locality_forward, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="event",
            name="locality",
        ),
        migrations.DeleteModel(
            name="Locality",
        ),
        migrations.RenameField(
            model_name="event",
            old_name="locality_name",
            new_name="locality",
        ),
    ]
