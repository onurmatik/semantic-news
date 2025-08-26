import logging
from django.conf import settings
import httpx
from openai import OpenAI as _OpenAI, AsyncOpenAI as _AsyncOpenAI

logger = logging.getLogger(__name__)


def _get_http_client():
    if not getattr(settings, "DEBUG", False):
        return None

    def log_request(request: httpx.Request):
        try:
            body = request.content.decode()
        except Exception:
            body = str(request.content)
        logger.debug("OpenAI request %s %s: %s", request.method, request.url, body)

    def log_response(response: httpx.Response):
        body = response.read().decode()
        logger.debug(
            "OpenAI response %s %s: %s", response.status_code, response.url, body
        )

    return httpx.Client(event_hooks={"request": [log_request], "response": [log_response]})


def _get_async_http_client():
    if not getattr(settings, "DEBUG", False):
        return None

    async def log_request(request: httpx.Request):
        try:
            body = request.content.decode()
        except Exception:
            body = str(request.content)
        logger.debug("OpenAI request %s %s: %s", request.method, request.url, body)

    async def log_response(response: httpx.Response):
        body = (await response.aread()).decode()
        logger.debug(
            "OpenAI response %s %s: %s", response.status_code, response.url, body
        )

    return httpx.AsyncClient(event_hooks={"request": [log_request], "response": [log_response]})


class OpenAI(_OpenAI):
    """OpenAI client that logs requests and responses when DEBUG is True."""

    def __init__(self, *args, **kwargs):
        if "http_client" not in kwargs:
            client = _get_http_client()
            if client is not None:
                kwargs["http_client"] = client
        super().__init__(*args, **kwargs)


class AsyncOpenAI(_AsyncOpenAI):
    """AsyncOpenAI client that logs requests and responses when DEBUG is True."""

    def __init__(self, *args, **kwargs):
        if "http_client" not in kwargs:
            client = _get_async_http_client()
            if client is not None:
                kwargs["http_client"] = client
        super().__init__(*args, **kwargs)
