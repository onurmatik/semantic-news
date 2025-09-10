from django.db import models


class TopicData(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='datas')
    url = models.URLField()
    name = models.CharField(max_length=200, blank=True, null=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Data for {self.topic}"


class TopicDataInsight(models.Model):
    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='data_insights'
    )
    insight = models.TextField()
    sources = models.ManyToManyField('TopicData', related_name='insights')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Insight for {self.topic}"


class TopicDataVisualization(models.Model):
    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='data_visualizations'
    )
    insight = models.ForeignKey(
        TopicDataInsight, on_delete=models.SET_NULL, null=True, blank=True, related_name='visualizations'
    )
    chart_type = models.CharField(max_length=50)
    chart_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Visualization for {self.topic}"
