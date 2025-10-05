from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0026_seed_topic_module_layout"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="topicmodulelayout",
            name="size_variant",
        ),
    ]
