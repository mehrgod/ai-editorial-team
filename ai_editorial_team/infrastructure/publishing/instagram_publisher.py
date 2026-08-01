from dataclasses import dataclass
import json
import os
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from dotenv import load_dotenv

from ai_editorial_team.domain.models import (
    PublicationRequest,
    PublicationResult,
)
from ai_editorial_team.domain.ports import SocialPublisher


DEFAULT_GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE_URL = "https://graph.instagram.com"


class InstagramPublishingError(RuntimeError):
    """Raised when Instagram publishing fails."""


class InstagramPublishingConfigurationError(InstagramPublishingError):
    """Raised when required Instagram publishing configuration is missing."""


class InstagramAuthenticationError(InstagramPublishingError):
    """Raised when Meta rejects the access token or account access."""


class InstagramMediaContainerError(InstagramPublishingError):
    """Raised when media container creation fails."""


class InstagramMediaPublishError(InstagramPublishingError):
    """Raised when media publishing fails."""


class InstagramPublicationLookupError(InstagramPublishingError):
    """Raised when the published media permalink cannot be resolved."""


@dataclass(frozen=True)
class InstagramPublishingConfig:
    instagram_professional_account_id: str
    meta_access_token: str
    graph_api_version: str = DEFAULT_GRAPH_API_VERSION

    @classmethod
    def from_env(cls) -> "InstagramPublishingConfig":
        load_dotenv()

        instagram_professional_account_id = os.environ.get(
            "INSTAGRAM_PROFESSIONAL_ACCOUNT_ID"
        )
        meta_access_token = os.environ.get("META_ACCESS_TOKEN")
        graph_api_version = (
            os.environ.get("GRAPH_API_VERSION") or DEFAULT_GRAPH_API_VERSION
        )

        missing = [
            name
            for name, value in [
                ("INSTAGRAM_PROFESSIONAL_ACCOUNT_ID", instagram_professional_account_id),
                ("META_ACCESS_TOKEN", meta_access_token),
            ]
            if not value
        ]
        if missing:
            raise InstagramPublishingConfigurationError(
                "Missing required Instagram publishing configuration: "
                + ", ".join(missing)
            )

        return cls(
            instagram_professional_account_id=instagram_professional_account_id,
            meta_access_token=meta_access_token,
            graph_api_version=graph_api_version,
        )


class InstagramGraphApi(Protocol):
    def create_media_container(self, caption: str, image_url: str) -> str:
        ...

    def publish_media_container(self, container_id: str) -> str:
        ...

    def fetch_publication_url(self, publication_id: str) -> str:
        ...


@dataclass(frozen=True)
class MetaInstagramGraphApi:
    config: InstagramPublishingConfig

    def create_media_container(self, caption: str, image_url: str) -> str:
        data = self._post_json(
            self._graph_url(f"/{self.config.instagram_professional_account_id}/media"),
            {
                "image_url": image_url,
                "caption": caption,
                "access_token": self.config.meta_access_token,
            },
        )
        container_id = data.get("id")
        if not container_id:
            raise InstagramMediaContainerError(
                "Instagram media container response did not include an id."
            )
        return str(container_id)

    def publish_media_container(self, container_id: str) -> str:
        data = self._post_json(
            self._graph_url(
                f"/{self.config.instagram_professional_account_id}/media_publish"
            ),
            {
                "creation_id": container_id,
                "access_token": self.config.meta_access_token,
            },
        )
        publication_id = data.get("id")
        if not publication_id:
            raise InstagramMediaPublishError(
                "Instagram publish response did not include an id."
            )
        return str(publication_id)

    def fetch_publication_url(self, publication_id: str) -> str:
        data = self._get_json(
            self._graph_url(f"/{publication_id}"),
            {
                "fields": "permalink",
                "access_token": self.config.meta_access_token,
            },
        )
        publication_url = data.get("permalink")
        if not publication_url:
            raise InstagramPublicationLookupError(
                "Instagram publication lookup did not include a permalink."
            )
        return str(publication_url)

    def _graph_url(self, path: str) -> str:
        return f"{GRAPH_API_BASE_URL}/{self.config.graph_api_version}{path}"

    def _post_json(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        encoded_body = urllib_parse.urlencode(payload).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=encoded_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "AI Editorial Team",
            },
            method="POST",
        )
        return self._request_json(request)

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        query_string = urllib_parse.urlencode(params)
        request = urllib_request.Request(
            f"{url}?{query_string}",
            headers={"User-Agent": "AI Editorial Team"},
            method="GET",
        )
        return self._request_json(request)

    def _request_json(self, request: urllib_request.Request) -> dict[str, Any]:
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                raw_body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            raise self._error_from_http_error(exc) from exc
        except urllib_error.URLError as exc:
            raise InstagramPublishingError(
                f"Instagram Graph API request failed: {exc.reason}"
            ) from exc

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise InstagramPublishingError(
                "Instagram Graph API returned invalid JSON."
            ) from exc

    def _error_from_http_error(
        self, exc: urllib_error.HTTPError
    ) -> InstagramPublishingError:
        body = exc.read().decode("utf-8") if exc.fp else ""
        message = _extract_meta_error_message(body) or exc.reason

        if exc.code in (401, 403):
            return InstagramAuthenticationError(
                f"Instagram authentication failed: {message}"
            )

        return InstagramPublishingError(
            f"Instagram Graph API request failed ({exc.code}): {message}"
        )


@dataclass(frozen=True)
class InstagramPublisher(SocialPublisher):
    """Publishes one Instagram image post using the Graph API."""

    api: InstagramGraphApi

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        try:
            container_id = self.api.create_media_container(
                caption=publication["caption"],
                image_url=publication["image_url"],
            )
        except InstagramAuthenticationError:
            raise
        except InstagramPublishingError as exc:
            raise InstagramMediaContainerError(
                f"Instagram media container creation failed: {exc}"
            ) from exc

        try:
            publication_id = self.api.publish_media_container(container_id)
        except InstagramAuthenticationError:
            raise
        except InstagramPublishingError as exc:
            raise InstagramMediaPublishError(
                f"Instagram media publishing failed: {exc}"
            ) from exc

        try:
            publication_url = self.api.fetch_publication_url(publication_id)
        except InstagramAuthenticationError:
            raise
        except InstagramPublishingError as exc:
            raise InstagramPublicationLookupError(
                f"Instagram publication URL lookup failed: {exc}"
            ) from exc

        return {
            "platform": "Instagram",
            "publication_id": publication_id,
            "publication_url": publication_url,
        }


def _extract_meta_error_message(body: str) -> str | None:
    if not body:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
        error_type = error.get("type")
        if error_type:
            return str(error_type)

    return body


def create_instagram_publisher_from_env() -> InstagramPublisher:
    config = InstagramPublishingConfig.from_env()
    return InstagramPublisher(
        api=MetaInstagramGraphApi(config),
    )
