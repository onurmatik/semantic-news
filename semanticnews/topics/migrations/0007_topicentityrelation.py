from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("topics", "0006_topicnarrative"),
    ]

    operations = [
        migrations.CreateModel(
            name="TopicEntityRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relations", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in_progress", "In progress"),
                            ("finished", "Finished"),
                            ("error", "Error"),
                        ],
                        default="in_progress",
                        max_length=20,
                    ),
                ),
                (
                    "topic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entity_relations",
                        to="topics.topic",
                    ),
                ),
            ],
        ),
    ]
