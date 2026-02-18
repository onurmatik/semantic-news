from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


class NewsRadarError(Exception):
    """Raised when NewsRadar API operations fail."""


@dataclass
class NewsRadarTopicPayload:
    topic_id: str
    title: str
    query: str
    raw: dict[str, Any]


class NewsRadarClient:
    """Minimal client for NewsRadar topic provisioning."""

    def __init__(self):
        self.base_url = (getattr(settings, "NEWSRADAR_BASE_URL", "") or "").rstrip("/")
        self.api_key = getattr(settings, "NEWSRADAR_API_KEY", "") or ""
        self.timeout = int(getattr(settings, "NEWSRADAR_TIMEOUT_SECONDS", 10))

        if not self.base_url:
            raise NewsRadarError("NEWSRADAR_BASE_URL is not configured.")
        if not self.api_key:
            raise NewsRadarError("NEWSRADAR_API_KEY is not configured.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise NewsRadarError(f"Request to NewsRadar failed: {exc}") from exc

        if response.status_code >= 400:
            message = response.text[:500]
            raise NewsRadarError(
                f"NewsRadar returned {response.status_code} for {path}: {message}"
            )

        try:
            return response.json()
        except ValueError:
            raise NewsRadarError("NewsRadar did not return valid JSON.")

    def get_me(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/auth/me")
        if not isinstance(payload, dict):
            raise NewsRadarError("Unexpected response payload from /api/auth/me")
        return payload

    def create_topic(self, *, title: str, query: str) -> NewsRadarTopicPayload:
        cleaned_title = (title or "").strip() or "Untitled topic"
        cleaned_query = (query or "").strip() or cleaned_title

        candidates = [
            {"title": cleaned_title, "query": cleaned_query},
            {"name": cleaned_title, "query": cleaned_query},
            {"title": cleaned_title, "queries": [cleaned_query]},
            {"name": cleaned_title, "queries": [cleaned_query]},
        ]

        last_error: NewsRadarError | None = None
        for body in candidates:
            try:
                payload = self._request("POST", "/api/topics/", json=body)
            except NewsRadarError as exc:
                last_error = exc
                continue

            if not isinstance(payload, dict):
                raise NewsRadarError("Unexpected response payload from /api/topics/")

            topic_id = str(
                payload.get("uuid")
                or payload.get("id")
                or payload.get("topic_uuid")
                or ""
            ).strip()
            if not topic_id:
                raise NewsRadarError("Could not determine created topic id from response.")

            resolved_title = str(payload.get("title") or payload.get("name") or cleaned_title)
            resolved_query = str(
                payload.get("query")
                or payload.get("search")
                or cleaned_query
            )

            return NewsRadarTopicPayload(
                topic_id=topic_id,
                title=resolved_title,
                query=resolved_query,
                raw=payload,
            )

        if last_error is not None:
            raise last_error
        raise NewsRadarError("Failed to create topic in NewsRadar.")
