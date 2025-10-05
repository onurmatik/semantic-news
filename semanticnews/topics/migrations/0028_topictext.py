# Generated manually by ChatGPT
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F


def convert_narratives_to_texts(apps, schema_editor):
    TopicModuleLayout = apps.get_model('topics', 'TopicModuleLayout')
    TopicText = apps.get_model('topics', 'TopicText')

    for layout in TopicModuleLayout.objects.filter(module_key='narratives'):
        topic = layout.topic
        placement = layout.placement
        display_order = layout.display_order

        texts = list(TopicText.objects.filter(topic=topic).order_by('created_at'))
        extra = max(len(texts) - 1, 0)
        if extra:
            TopicModuleLayout.objects.filter(
                topic=topic,
                placement=placement,
                display_order__gt=display_order,
            ).update(display_order=F('display_order') + extra)

        layout.delete()

        for index, text in enumerate(texts):
            TopicModuleLayout.objects.create(
                topic=topic,
                module_key=f'text:{text.id}',
                placement=placement,
                display_order=display_order + index,
            )

    for text in TopicText.objects.all():
        module_key = f'text:{text.id}'
        exists = TopicModuleLayout.objects.filter(
            topic=text.topic,
            module_key=module_key,
        ).exists()
        if not exists:
            max_order = (
                TopicModuleLayout.objects
                .filter(topic=text.topic, placement=TopicModuleLayout.PLACEMENT_PRIMARY)
                .aggregate(models.Max('display_order'))
                .get('display_order__max')
            )
            TopicModuleLayout.objects.create(
                topic=text.topic,
                module_key=module_key,
                placement=TopicModuleLayout.PLACEMENT_PRIMARY,
                display_order=(max_order or 0) + 1,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0027_remove_topicmodulelayout_size'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TopicNarrative',
            new_name='TopicText',
        ),
        migrations.RenameField(
            model_name='topictext',
            old_name='narrative',
            new_name='content',
        ),
        migrations.AddField(
            model_name='topictext',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='topictext',
            name='content',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='topictext',
            name='status',
            field=models.CharField(
                choices=[
                    ('in_progress', 'In progress'),
                    ('finished', 'Finished'),
                    ('error', 'Error'),
                ],
                default='finished',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='topictext',
            name='topic',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='texts',
                to='topics.topic',
            ),
        ),
        migrations.AlterModelOptions(
            name='topictext',
            options={'ordering': ['created_at']},
        ),
        migrations.RunPython(convert_narratives_to_texts, migrations.RunPython.noop),
    ]
