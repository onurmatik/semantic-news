from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0006_topicsection_widget_registry"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicsection",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="topicsection",
            name="execution_state",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
