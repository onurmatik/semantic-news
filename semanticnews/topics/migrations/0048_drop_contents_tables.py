from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0047_alter_topicdata_options_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=";\n".join(
                [
                    "DROP TABLE IF EXISTS contents_contentevent CASCADE",
                    "DROP TABLE IF EXISTS contents_content CASCADE",
                    "DROP TABLE IF EXISTS contents_source CASCADE",
                ]
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
