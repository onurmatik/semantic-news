from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0045_topic_widget_display_order"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TopicModuleLayout",
        ),
    ]
