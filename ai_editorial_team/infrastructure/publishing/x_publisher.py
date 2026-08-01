from dataclasses import dataclass
import json
import os
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from dotenv import load_dotenv

from ai_editorial_team.domain.models import (
    PublicationRequest,
    PublicationResult,
)
from ai_editorial_team.domain.ports import SocialPublisher


X_API_BASE_URL = "https://api.x.com"


class XPublishingError(RuntimeError):
    """Raised when X publishing fails."""


class XPublishingConfigurationError(XPublishingError):
    """Raised when required X publishing configuration is missing."""


class XAuthenticationError(XPublishingError):
    """Raised when X rejects the user access token."""


class XPostCreationError(XPublishingError):
    """Raised when X post creation fails."""


class XPublicationResponseError(XPublishingError):
    """Raised when X returns an incomplete response."""


@dataclass(frozen=True)
class XPublishingConfig:
    user_access_token: str

    @classmethod
    def from_env(cls) -> "XPublishingConfig":
        load_dotenv()

        user_access_token = os.environ.get("X_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise XPublishingConfigurationError(
                "Missing required X publishing configuration: X_USER_ACCESS_TOKEN"
            )

        return cls(user_access_token=user_access_token)


class XApi(Protocol):
    def create_post(self, text: str) -> str:
        ...


@dataclass(frozen=True)
class XHttpApi:
    config: XPublishingConfig

    def create_post(self, text: str) -> str:
        data = self._post_json(
            f"{X_API_BASE_URL}/2/tweets",
            {"text": text},
        )
        post_id = data.get("data", {}).get("id")
        if not post_id:
            raise XPublicationResponseError(
                "X post creation response did not include an id."
            )
        return str(post_id)

    def _post_json(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        encoded_body = json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=encoded_body,
            headers={
                "Authorization": f"Bearer {self.config.user_access_token}",
                "Content-Type": "application/json",
                "User-Agent": "AI Editorial Team",
            },
            method="POST",
        )
        return self._request_json(request)

    def _request_json(self, request: urllib_request.Request) -> dict[str, Any]:
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                raw_body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            raise self._error_from_http_error(exc) from exc
        except urllib_error.URLError as exc:
            raise XPublishingError(
                f"X API request failed: {exc.reason}"
            ) from exc

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise XPublishingError("X API returned invalid JSON.") from exc

    def _error_from_http_error(
        self, exc: urllib_error.HTTPError
    ) -> XPublishingError:
        body = exc.read().decode("utf-8") if exc.fp else ""
        message = _extract_x_error_message(body) or exc.reason

        if exc.code in (401, 403):
            return XAuthenticationError(
                f"X authentication failed: {message}"
            )

        return XPostCreationError(
            f"X post creation failed ({exc.code}): {message}"
        )


@dataclass(frozen=True)
class XPublisher(SocialPublisher):
    """Publishes one text-only X post."""

    api: XApi

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        text = publication.get("text")
        if not text:
            raise XPostCreationError("X publishing requires post text.")

        try:
            post_id = self.api.create_post(text)
        except XAuthenticationError:
            raise
        except XPublishingError as exc:
            raise XPostCreationError(f"X post creation failed: {exc}") from exc

        return {
            "platform": "X",
            "publication_id": post_id,
            "publication_url": f"https://x.com/i/web/status/{post_id}",
        }


def _extract_x_error_message(body: str) -> str | None:
    if not body:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(payload.get("detail"), str):
        return str(payload["detail"])
    if isinstance(payload.get("title"), str):
        return str(payload["title"])

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        first_error = errors[0]
        if isinstance(first_error, dict):
            message = first_error.get("message") or first_error.get("detail")
            if message:
                return str(message)

    return body


def create_x_publisher_from_env() -> XPublisher:
    config = XPublishingConfig.from_env()
    return XPublisher(api=XHttpApi(config))
