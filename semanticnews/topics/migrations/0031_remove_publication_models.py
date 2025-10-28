from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0030_remove_topicpublisheddatainsight_publication_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="topic",
            name="latest_publication",
        ),
        migrations.DeleteModel(
            name="TopicPublicationSnapshot",
        ),
        migrations.DeleteModel(
            name="TopicPublicationModule",
        ),
        migrations.DeleteModel(
            name="TopicPublication",
        ),
    ]
