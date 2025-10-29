from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0044_topictitle_remove_topicevent_created_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicdata",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topicdatainsight",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topicdatavisualization",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topicdocument",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddIndex(
            model_name="topicdocument",
            index=models.Index(
                fields=["display_order"],
                name="topics_topicdoc_disp_ord_idx",
            ),
        ),
        migrations.AddField(
            model_name="topicimage",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topictext",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topictweet",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddField(
            model_name="topicwebpage",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
        migrations.AddIndex(
            model_name="topicwebpage",
            index=models.Index(
                fields=["display_order"],
                name="topics_topicweb_disp_ord_idx",
            ),
        ),
        migrations.AddField(
            model_name="topicyoutubevideo",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Ordering position within the topic's content column.",
            ),
        ),
    ]
