from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0048_drop_contents_tables"),
        ("widgets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TopicSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("content", models.JSONField(blank=True, null=True)),
                ("topic", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sections", to="topics.topic")),
                ("widget", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sections", to="widgets.widget")),
            ],
            options={
                "ordering": ("display_order", "id"),
            },
        ),
    ]
