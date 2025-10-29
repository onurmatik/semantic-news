from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("widgets", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="topicwidget",
            options={"ordering": ("display_order", "id")},
        ),
        migrations.RemoveField(
            model_name="topicwidget",
            name="placement",
        ),
    ]
