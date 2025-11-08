from django.db import migrations, models


def copy_widget_name(apps, schema_editor):
    TopicSection = apps.get_model("topics", "TopicSection")
    Widget = apps.get_model("widgets", "Widget")
    db_alias = schema_editor.connection.alias

    widget_lookup = {
        widget.pk: widget.name
        for widget in Widget.objects.using(db_alias).all()
    }

    sections = TopicSection.objects.using(db_alias).all()
    for section in sections.iterator():
        widget_id = getattr(section, "widget_id", None)
        if not widget_id:
            continue
        widget_name = widget_lookup.get(widget_id)
        if not widget_name:
            continue
        section.widget_name = widget_name
        section.save(update_fields=["widget_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("topics", "0005_remove_topicsection_error_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicsection",
            name="widget_name",
            field=models.CharField(default="", max_length=100, db_index=True),
            preserve_default=False,
        ),
        migrations.RunPython(copy_widget_name, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="topicsection",
            name="widget",
        ),
    ]
