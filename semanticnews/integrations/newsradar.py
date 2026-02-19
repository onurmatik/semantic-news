from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


class NewsRadarError(Exception):
    """Raised when NewsRadar API operations fail."""


@dataclass
class NewsRadarTopicPayload:
    topic_uuid: str
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

    def _extract_topic_payload(self, payload: Any, *, endpoint: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(payload, dict):
            raise NewsRadarError(f"Unexpected response payload from {endpoint}")
        topic = payload.get("topic") if isinstance(payload.get("topic"), dict) else payload
        if not isinstance(topic, dict):
            raise NewsRadarError(f"Unexpected topic payload from {endpoint}")
        return payload, topic

    def create_topic(self, *, title: str, query: str) -> NewsRadarTopicPayload:
        cleaned_title = (title or "").strip()
        cleaned_query = (query or "").strip() or cleaned_title
        if not cleaned_query:
            raise NewsRadarError("Topic query cannot be empty.")

        payload = self._request(
            "POST",
            "/api/topics/",
            json={
                "queries": [cleaned_query],
                "additional_queries_mode": "auto",
            },
        )
        raw_payload, topic = self._extract_topic_payload(payload, endpoint="/api/topics/")

        topic_uuid = str(
            topic.get("uuid")
            or topic.get("topic_uuid")
            or ""
        ).strip()
        if not topic_uuid:
            raise NewsRadarError("Could not determine created topic uuid from response.")

        resolved_title = str(topic.get("title") or topic.get("name") or cleaned_title or cleaned_query)
        topic_queries = topic.get("queries") if isinstance(topic.get("queries"), list) else None
        resolved_query = str(
            topic.get("query")
            or topic.get("search")
            or (topic_queries[0] if topic_queries else "")
            or cleaned_query
        )

        return NewsRadarTopicPayload(
            topic_uuid=topic_uuid,
            title=resolved_title,
            query=resolved_query,
            raw=raw_payload,
        )

    def update_topic(self, *, topic_uuid: str, title: str, query: str | None = None) -> NewsRadarTopicPayload:
        cleaned_topic_uuid = (topic_uuid or "").strip()
        cleaned_title = (title or "").strip()
        cleaned_query = (query or "").strip() or cleaned_title
        if not cleaned_topic_uuid:
            raise NewsRadarError("Topic uuid cannot be empty.")
        if not cleaned_query:
            raise NewsRadarError("Topic query cannot be empty.")

        payload = self._request(
            "PATCH",
            f"/api/topics/{cleaned_topic_uuid}",
            json={
                "queries": [cleaned_query],
                "additional_queries_mode": "auto",
            },
        )
        raw_payload, topic = self._extract_topic_payload(payload, endpoint=f"/api/topics/{cleaned_topic_uuid}")

        resolved_uuid = str(topic.get("uuid") or topic.get("topic_uuid") or cleaned_topic_uuid).strip()
        resolved_title = str(topic.get("title") or topic.get("name") or cleaned_title or cleaned_query)
        topic_queries = topic.get("queries") if isinstance(topic.get("queries"), list) else None
        resolved_query = str(
            topic.get("query")
            or topic.get("search")
            or (topic_queries[0] if topic_queries else "")
            or cleaned_query
        )

        return NewsRadarTopicPayload(
            topic_uuid=resolved_uuid,
            title=resolved_title,
            query=resolved_query,
            raw=raw_payload,
        )
