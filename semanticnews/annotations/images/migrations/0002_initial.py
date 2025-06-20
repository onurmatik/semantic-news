# Generated by Django 5.2.1 on 2025-06-17 12:54

import django.db.models.deletion
import pgvector.django.indexes
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('topic_images', '0001_initial'),
        ('topics', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='topicimage',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='images', to='topics.topic'),
        ),
        migrations.AddIndex(
            model_name='topicimage',
            index=pgvector.django.indexes.HnswIndex(ef_construction=64, fields=['embedding'], m=16, name='topicimage_embedding_hnsw', opclasses=['vector_l2_ops']),
        ),
    ]
