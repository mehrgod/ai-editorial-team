from base64 import b64encode
from dataclasses import dataclass
import json
import mimetypes
import os
from pathlib import Path
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


X_API_BASE_URL = "https://api.x.com"
X_OAUTH_TOKEN_URL = "https://api.x.com/2/oauth2/token"
X_SECRETS_MANAGER_SECRET_NAME = "ai-editorial-team/prod"


class XPublishingError(RuntimeError):
    """Raised when X publishing fails."""


class XPublishingConfigurationError(XPublishingError):
    """Raised when required X publishing configuration is missing."""


class XAuthenticationError(XPublishingError):
    """Raised when X rejects the user access token."""


class XTokenRefreshError(XPublishingError):
    """Raised when X OAuth token refresh fails."""


class XTokenPersistenceError(XPublishingError):
    """Raised when refreshed X tokens cannot be persisted."""


class XPostCreationError(XPublishingError):
    """Raised when X post creation fails."""


class XMediaUploadError(XPublishingError):
    """Raised when X media upload fails."""


class XPublicationResponseError(XPublishingError):
    """Raised when X returns an incomplete response."""


@dataclass(frozen=True)
class XPublishingConfig:
    user_access_token: str
    refresh_token: str
    client_id: str
    client_secret: str
    secrets_manager_secret_name: str = X_SECRETS_MANAGER_SECRET_NAME

    @classmethod
    def from_env(cls) -> "XPublishingConfig":
        load_dotenv()

        user_access_token = (
            os.environ.get("X_ACCESS_TOKEN")
            or os.environ.get("X_USER_ACCESS_TOKEN")
        )
        refresh_token = os.environ.get("X_REFRESH_TOKEN")
        client_id = os.environ.get("X_CLIENT_ID")
        client_secret = os.environ.get("X_CLIENT_SECRET")

        missing = [
            name
            for name, value in [
                ("X_ACCESS_TOKEN", user_access_token),
                ("X_REFRESH_TOKEN", refresh_token),
                ("X_CLIENT_ID", client_id),
                ("X_CLIENT_SECRET", client_secret),
            ]
            if not value
        ]
        if missing:
            raise XPublishingConfigurationError(
                "Missing required X publishing configuration: "
                + ", ".join(missing)
            )

        return cls(
            user_access_token=user_access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )


@dataclass(frozen=True)
class XTokenRefreshResult:
    access_token: str
    refresh_token: str | None = None


class XApi(Protocol):
    def upload_media(self, local_file_path: str) -> str:
        ...

    def create_post(self, text: str, media_ids: list[str]) -> str:
        ...


@dataclass(frozen=True)
class XHttpApi:
    config: XPublishingConfig

    def upload_media(self, local_file_path: str) -> str:
        image_path = Path(local_file_path)
        media_type = mimetypes.guess_type(image_path)[0] or "image/png"
        try:
            image_bytes = image_path.read_bytes()
        except OSError as exc:
            raise XMediaUploadError(
                f"X media upload could not read image file {image_path}: {exc}"
            ) from exc

        data = self._post_json(
            f"{X_API_BASE_URL}/2/media/upload",
            {
                "media": b64encode(image_bytes).decode("ascii"),
                "media_category": "tweet_image",
                "media_type": media_type,
            },
        )
        media_id = data.get("data", {}).get("id")
        if not media_id:
            raise XPublicationResponseError(
                "X media upload response did not include an id."
            )
        return str(media_id)

    def create_post(self, text: str, media_ids: list[str]) -> str:
        data = self._post_json(
            f"{X_API_BASE_URL}/2/tweets",
            {
                "text": text,
                "media": {"media_ids": media_ids},
            },
        )
        post_id = data.get("data", {}).get("id")
        if not post_id:
            raise XPublicationResponseError(
                "X post creation response did not include an id."
            )
        return str(post_id)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
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
    """Publishes one X post with three attached images."""

    api: XApi

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        text = publication.get("text")
        if not text:
            raise XPostCreationError("X publishing requires post text.")
        if len(text) > 250:
            raise XPostCreationError(
                "X publishing requires post text <= 250 characters."
            )

        image_paths = publication.get("image_paths") or []
        if len(image_paths) != 3:
            raise XMediaUploadError("X publishing requires exactly 3 image paths.")
        for image_path in image_paths:
            if not Path(image_path).is_file():
                raise XMediaUploadError(
                    f"X publishing image file was not found: {image_path}"
                )

        try:
            media_ids = [
                self.api.upload_media(image_path)
                for image_path in image_paths
            ]
        except XAuthenticationError:
            raise
        except XPublishingError as exc:
            raise XMediaUploadError(f"X media upload failed: {exc}") from exc

        try:
            post_id = self.api.create_post(text, media_ids)
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
    refreshed_tokens = _refresh_x_oauth_token(config)
    refresh_token = refreshed_tokens.refresh_token or config.refresh_token
    _update_x_tokens_in_secrets_manager(
        secret_id=config.secrets_manager_secret_name,
        access_token=refreshed_tokens.access_token,
        refresh_token=refresh_token,
    )
    return XPublisher(
        api=XHttpApi(
            XPublishingConfig(
                user_access_token=refreshed_tokens.access_token,
                refresh_token=refresh_token,
                client_id=config.client_id,
                client_secret=config.client_secret,
                secrets_manager_secret_name=config.secrets_manager_secret_name,
            )
        )
    )


def _refresh_x_oauth_token(config: XPublishingConfig) -> XTokenRefreshResult:
    basic_auth = b64encode(
        f"{config.client_id}:{config.client_secret}".encode("utf-8")
    ).decode("ascii")
    body = urllib_parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": config.refresh_token,
            "client_id": config.client_id,
        }
    ).encode("utf-8")
    request = urllib_request.Request(
        X_OAUTH_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AI Editorial Team",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=30) as response:
            raw_body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        message = _extract_x_error_message(body) or exc.reason
        raise XTokenRefreshError(f"X OAuth token refresh failed: {message}") from exc
    except urllib_error.URLError as exc:
        raise XTokenRefreshError(
            f"X OAuth token refresh request failed: {exc.reason}"
        ) from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise XTokenRefreshError(
            "X OAuth token refresh returned invalid JSON."
        ) from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise XTokenRefreshError(
            "X OAuth token refresh response did not include an access_token."
        )

    refresh_token = payload.get("refresh_token")
    return XTokenRefreshResult(
        access_token=str(access_token),
        refresh_token=str(refresh_token) if refresh_token else None,
    )


def _update_x_tokens_in_secrets_manager(
    *, secret_id: str, access_token: str, refresh_token: str
) -> None:
    import boto3

    client = boto3.client("secretsmanager")
    _update_x_tokens_in_secret(
        client=client,
        secret_id=secret_id,
        access_token=access_token,
        refresh_token=refresh_token,
    )


def _update_x_tokens_in_secret(
    *, client, secret_id: str, access_token: str, refresh_token: str
) -> None:
    try:
        response = client.get_secret_value(SecretId=secret_id)
    except Exception as exc:
        raise XTokenPersistenceError(
            f"Could not read Secrets Manager secret {secret_id}: {exc}"
        ) from exc

    secret_string = response.get("SecretString")
    if not secret_string:
        raise XTokenPersistenceError(
            f"Secrets Manager secret {secret_id} does not contain a JSON string."
        )

    try:
        secret_payload = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise XTokenPersistenceError(
            f"Secrets Manager secret {secret_id} does not contain valid JSON."
        ) from exc

    if not isinstance(secret_payload, dict):
        raise XTokenPersistenceError(
            f"Secrets Manager secret {secret_id} must contain a JSON object."
        )

    secret_payload["X_ACCESS_TOKEN"] = access_token
    secret_payload["X_REFRESH_TOKEN"] = refresh_token

    try:
        client.put_secret_value(
            SecretId=secret_id,
            SecretString=json.dumps(secret_payload),
        )
    except Exception as exc:
        raise XTokenPersistenceError(
            f"Could not update X tokens in Secrets Manager secret {secret_id}: {exc}"
        ) from exc
