def update_recap(self):
    # Create a TopicRecap instance based on related content;
    # triggered when new content is added to the topic
    content_md = f'# {self.name}\n\n'

    topic_articles = TopicArticle.objects.filter(topic=self).select_related('article')
    if topic_articles.exists():
        content_md += '## Articles\n\n'
        for topic_article in topic_articles:
            article = topic_article.article
            content_md += f"### {article.title}\n{article.summary}\n\n"

    topic_videos = TopicVideo.objects.filter(
        topic=self,
        processed=True,
        video_chunk__isnull=False
    ) \
        .exclude(video_chunk__revised_text__isnull=True) \
        .select_related('video_chunk__transcript__video__channel')

    if topic_videos.exists():
        content_md += '## Video comment snippets\n\n'
        for topic_video in topic_videos:
            video_chunk = topic_video.video_chunk
            video = video_chunk.transcript.video
            content_md += f"### {video.channel.title}\n{video_chunk.revised_text}\n\n"

    agent = TopicRecapAgent()
    response = async_to_sync(agent.run)(content_md)

    TopicRecap.objects.create(
        topic=self,
        recap=response.recap_tr,
        recap_en=response.recap_en,
    )

