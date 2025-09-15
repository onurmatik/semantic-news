from ninja import Router, Schema
from ninja.errors import HttpError
import requests

from ...models import Topic
from .models import TopicSocialEmbed

router = Router()


class EmbedCreateRequest(Schema):
    topic_uuid: str
    url: str


class EmbedCreateResponse(Schema):
    id: int
    provider: str
    url: str
    html: str


def _detect_provider(url: str) -> str:
    if 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    return ''


def _fetch_twitter_embed(url: str) -> str:
    res = requests.get('https://publish.twitter.com/oembed', params={'url': url, 'dnt': 'true'})
    res.raise_for_status()
    data = res.json()
    return data.get('html', '')


@router.post('/create', response=EmbedCreateResponse)
def create_embed(request, payload: EmbedCreateRequest):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        raise HttpError(401, 'Unauthorized')

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, 'Topic not found')

    if topic.created_by_id != user.id:
        raise HttpError(403, 'Forbidden')

    provider = _detect_provider(payload.url)
    if provider != 'twitter':
        raise HttpError(400, 'Unsupported provider')

    try:
        html = _fetch_twitter_embed(payload.url)
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(502, 'Embed fetch failed') from exc

    embed = TopicSocialEmbed.objects.create(
        topic=topic,
        provider=provider,
        url=payload.url,
        html=html,
    )
    return EmbedCreateResponse(id=embed.id, provider=provider, url=embed.url, html=embed.html)
