from dataclasses import dataclass
import json
import logging
import os
import time
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
CONTAINER_READY_STATUS = "FINISHED"
CONTAINER_TERMINAL_FAILURE_STATUSES = {"ERROR", "EXPIRED"}
CONTAINER_STATUS_ATTEMPTS = 26
CONTAINER_STATUS_DELAY_SECONDS = 12
MEDIA_PUBLISH_ATTEMPTS = 3
MEDIA_PUBLISH_RETRY_DELAY_SECONDS = 10
MEDIA_ID_NOT_AVAILABLE_MESSAGE = "Media ID is not available"


logger = logging.getLogger(__name__)


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
    def create_carousel_item_container(self, image_url: str) -> str:
        ...

    def create_carousel_container(
        self, caption: str, child_container_ids: list[str]
    ) -> str:
        ...

    def fetch_container_status(self, container_id: str) -> str:
        ...

    def publish_media_container(self, container_id: str) -> str:
        ...

    def fetch_publication_url(self, publication_id: str) -> str:
        ...


@dataclass(frozen=True)
class MetaInstagramGraphApi:
    config: InstagramPublishingConfig

    def create_carousel_item_container(self, image_url: str) -> str:
        data = self._post_json(
            self._graph_url(f"/{self.config.instagram_professional_account_id}/media"),
            {
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": self.config.meta_access_token,
            },
        )
        container_id = data.get("id")
        if not container_id:
            raise InstagramMediaContainerError(
                "Instagram carousel item container response did not include an id."
            )
        return str(container_id)

    def create_carousel_container(
        self, caption: str, child_container_ids: list[str]
    ) -> str:
        data = self._post_json(
            self._graph_url(f"/{self.config.instagram_professional_account_id}/media"),
            {
                "media_type": "CAROUSEL",
                "children": ",".join(child_container_ids),
                "caption": caption,
                "access_token": self.config.meta_access_token,
            },
        )
        container_id = data.get("id")
        if not container_id:
            raise InstagramMediaContainerError(
                "Instagram carousel parent container response did not include an id."
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

    def fetch_container_status(self, container_id: str) -> str:
        data = self._get_json(
            self._graph_url(f"/{container_id}"),
            {
                "fields": "status_code,status",
                "access_token": self.config.meta_access_token,
            },
        )
        status_code = data.get("status_code")
        if not status_code:
            raise InstagramMediaContainerError(
                "Instagram media container status response did not include "
                "status_code."
            )
        return str(status_code)

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
    """Publishes one Instagram carousel using the Graph API."""

    api: InstagramGraphApi
    status_attempts: int = CONTAINER_STATUS_ATTEMPTS
    status_delay_seconds: int = CONTAINER_STATUS_DELAY_SECONDS

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        caption = publication.get("caption")
        if not caption:
            raise InstagramMediaContainerError(
                "Instagram carousel publishing requires a caption."
            )

        image_urls = publication.get("image_urls") or []
        if len(image_urls) != 3:
            raise InstagramMediaContainerError(
                "Instagram carousel publishing requires exactly 3 image URLs."
            )
        if any(not image_url for image_url in image_urls):
            raise InstagramMediaContainerError(
                "Instagram carousel publishing requires every image URL to be set."
            )

        try:
            child_container_ids = [
                self.api.create_carousel_item_container(image_url)
                for image_url in image_urls
            ]
        except InstagramAuthenticationError:
            raise
        except InstagramPublishingError as exc:
            raise InstagramMediaContainerError(
                f"Instagram carousel item container creation failed: {exc}"
            ) from exc

        for child_container_id in child_container_ids:
            self._wait_until_container_ready(child_container_id)

        try:
            parent_container_id = self.api.create_carousel_container(
                caption=caption,
                child_container_ids=child_container_ids,
            )
        except InstagramAuthenticationError:
            raise
        except InstagramPublishingError as exc:
            raise InstagramMediaContainerError(
                f"Instagram carousel parent container creation failed: {exc}"
            ) from exc

        self._wait_until_container_ready(parent_container_id)

        publication_id = self._publish_ready_container(parent_container_id)

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

    def _wait_until_container_ready(self, container_id: str) -> None:
        last_status = ""
        for attempt in range(self.status_attempts):
            try:
                last_status = self.api.fetch_container_status(container_id)
            except InstagramAuthenticationError:
                raise
            except InstagramPublishingError as exc:
                raise InstagramMediaContainerError(
                    f"Instagram media container status check failed: {exc}"
                ) from exc

            logger.info(
                "Instagram media container %s status: %s (%s/%s)",
                container_id,
                last_status,
                attempt + 1,
                self.status_attempts,
            )

            if last_status == CONTAINER_READY_STATUS:
                return
            if last_status in CONTAINER_TERMINAL_FAILURE_STATUSES:
                raise InstagramMediaContainerError(
                    "Instagram media container failed while processing: "
                    f"{last_status}"
                )

            if attempt < self.status_attempts - 1:
                time.sleep(self.status_delay_seconds)

        raise InstagramMediaContainerError(
            "Instagram media container was not ready to publish after "
            f"{self.status_attempts} checks. Last status: {last_status}."
        )

    def _publish_ready_container(self, container_id: str) -> str:
        for attempt in range(MEDIA_PUBLISH_ATTEMPTS):
            try:
                return self.api.publish_media_container(container_id)
            except InstagramAuthenticationError:
                raise
            except InstagramPublishingError as exc:
                if (
                    _is_media_id_not_available_error(exc)
                    and attempt < MEDIA_PUBLISH_ATTEMPTS - 1
                ):
                    logger.info(
                        "Instagram media container %s was FINISHED but not "
                        "available to publish yet (%s/%s). Retrying in %s seconds.",
                        container_id,
                        attempt + 1,
                        MEDIA_PUBLISH_ATTEMPTS,
                        MEDIA_PUBLISH_RETRY_DELAY_SECONDS,
                    )
                    time.sleep(MEDIA_PUBLISH_RETRY_DELAY_SECONDS)
                    continue

                raise InstagramMediaPublishError(
                    f"Instagram media publishing failed: {exc}"
                ) from exc

        raise InstagramMediaPublishError(
            f"Instagram media publishing failed for container {container_id}."
        )


def _is_media_id_not_available_error(exc: InstagramPublishingError) -> bool:
    return MEDIA_ID_NOT_AVAILABLE_MESSAGE in str(exc)


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
