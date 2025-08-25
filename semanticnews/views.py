from django.shortcuts import render
from .agenda.models import Event
from .topics.models import Topic


def home(request):
    recent_events = Event.objects.filter(status='published').order_by('-date')[:5]
    return render(request, 'home.html', {
        'events': recent_events,
        'topics': Topic.objects.all(),
    })


def search_results(request):
    recommendation_count = 3
    search_query = request.GET.get('q', '').strip()

    if not search_query:
        return render(request, 'search_results.html',
                      {'search_query': search_query})

    user_obj = request.user if request.user.is_authenticated else None
    search_term, created = TopicSearchTerm.objects.get_or_create(
        term=search_query,
        user=user_obj,
    )

    if search_term.embedding is not None:
        similar_topics = Topic.objects.filter(embedding__isnull=False) \
                             .filter(status='p') \
                             .order_by(L2Distance('embedding', search_term.embedding))
        recommended_keywords = (
            Keyword.objects
            .filter(embedding__isnull=False)
            .annotate(distance=L2Distance('embedding', search_term.embedding))
            .order_by('distance')[:10]
        )
        rec_articles, rec_rss_items, rec_videos = build_recommendations(
            embedding=search_term.embedding,
            limit=recommendation_count,
        )
    else:
        # no embedding → no recommendations
        similar_topics = Topic.objects.none()
        recommended_keywords = Keyword.objects.none()
        rec_articles = rec_rss_items = rec_videos = []

    context = {
        'search_query': search_query,
        'similar_topics': similar_topics[:20],
        'recommended_keywords': recommended_keywords,
        'recommended_articles': rec_articles,
        'recommended_rss_items': rec_rss_items,
        'recommended_videos': rec_videos,
    }

    return render(request, 'search_results.html', context)
