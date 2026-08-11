import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import parse as urllib_parse

from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.x_publisher import (
    XMediaUploadError,
    XPostCreationError,
    XPublisher,
    XPublishingConfig,
    XTokenRefreshResult,
    create_x_publisher_from_env,
    _refresh_x_oauth_token,
    _update_x_tokens_in_secret,
)


class FakeXApi:
    def __init__(self) -> None:
        self.upload_calls = []
        self.create_calls = []

    def upload_media(self, local_file_path: str) -> str:
        self.upload_calls.append(local_file_path)
        return f"media-{len(self.upload_calls)}"

    def create_post(self, text: str, media_ids: list[str]) -> str:
        self.create_calls.append({"text": text, "media_ids": media_ids})
        return "1234567890"


class ExplodingXApi:
    def upload_media(self, local_file_path: str) -> str:
        raise XMediaUploadError("upload failed")

    def create_post(self, text: str, media_ids: list[str]) -> str:
        raise XPostCreationError("post failed")


class ExplodingPostXApi(FakeXApi):
    def create_post(self, text: str, media_ids: list[str]) -> str:
        raise XPostCreationError("post failed")


class FakeTokenResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json_dumps(self._payload).encode("utf-8")


class RecordingSecretsManagerClient:
    def __init__(self, secret_payload: dict) -> None:
        self.secret_payload = secret_payload
        self.get_calls = []
        self.put_calls = []

    def get_secret_value(self, SecretId: str) -> dict:
        self.get_calls.append(SecretId)
        return {"SecretString": json_dumps(self.secret_payload)}

    def put_secret_value(self, SecretId: str, SecretString: str) -> None:
        self.put_calls.append(
            {"SecretId": SecretId, "SecretString": SecretString}
        )


class XPublishingTests(unittest.TestCase):
    def test_x_publisher_conforms_to_social_publisher_port(self):
        publisher = XPublisher(api=FakeXApi())

        self.assertIsInstance(publisher, SocialPublisher)

    def test_images_are_uploaded_and_media_ids_are_attached_in_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths = _create_image_files(temp_dir)
            api = FakeXApi()
            publisher = XPublisher(api=api)

            result = publisher.publish(
                {
                    "text": "1/ Sports 2/ AI 3/ Finance",
                    "image_paths": image_paths,
                }
            )

            self.assertEqual(api.upload_calls, image_paths)
            self.assertEqual(
                api.create_calls,
                [
                    {
                        "text": "1/ Sports 2/ AI 3/ Finance",
                        "media_ids": ["media-1", "media-2", "media-3"],
                    }
                ],
            )
            self.assertEqual(
                result,
                {
                    "platform": "X",
                    "publication_id": "1234567890",
                    "publication_url": "https://x.com/i/web/status/1234567890",
                },
            )

    def test_x_api_failures_produce_clear_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths = _create_image_files(temp_dir)
            publisher = XPublisher(api=ExplodingXApi())

            with self.assertRaises(XMediaUploadError) as context:
                publisher.publish(
                    {
                        "text": "1/ Sports 2/ AI 3/ Finance",
                        "image_paths": image_paths,
                    }
                )

            self.assertIn("X media upload failed", str(context.exception))

    def test_post_creation_failures_produce_clear_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths = _create_image_files(temp_dir)
            publisher = XPublisher(api=ExplodingPostXApi())

            with self.assertRaises(XPostCreationError) as context:
                publisher.publish(
                    {
                        "text": "1/ Sports 2/ AI 3/ Finance",
                        "image_paths": image_paths,
                    }
                )

            self.assertIn("X post creation failed", str(context.exception))

    def test_missing_image_file_produces_clear_error(self):
        publisher = XPublisher(api=FakeXApi())

        with self.assertRaises(XMediaUploadError) as context:
            publisher.publish(
                {
                    "text": "1/ Sports 2/ AI 3/ Finance",
                    "image_paths": [
                        "/tmp/missing-rank-1.png",
                        "/tmp/missing-rank-2.png",
                        "/tmp/missing-rank-3.png",
                    ],
                }
            )

        self.assertIn("image file was not found", str(context.exception))

    def test_refresh_token_request_uses_refresh_token_grant(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeTokenResponse(
                {
                    "access_token": "fresh-access-token",
                    "refresh_token": "rotated-refresh-token",
                }
            )

        with patch(
            "ai_editorial_team.infrastructure.publishing.x_publisher."
            "urllib_request.urlopen",
            fake_urlopen,
        ):
            result = _refresh_x_oauth_token(_x_config())

        self.assertEqual(result.access_token, "fresh-access-token")
        self.assertEqual(result.refresh_token, "rotated-refresh-token")
        request_body = urllib_parse.parse_qs(
            captured["request"].data.decode("utf-8")
        )
        self.assertEqual(request_body["grant_type"], ["refresh_token"])
        self.assertEqual(request_body["refresh_token"], ["old-refresh-token"])
        self.assertEqual(request_body["client_id"], ["client-id"])
        self.assertTrue(captured["request"].get_header("Authorization").startswith("Basic "))

    def test_secret_update_preserves_unrelated_keys(self):
        client = RecordingSecretsManagerClient(
            {
                "OPENAI_API_KEY": "keep-me",
                "X_ACCESS_TOKEN": "old-access-token",
                "X_REFRESH_TOKEN": "old-refresh-token",
            }
        )

        _update_x_tokens_in_secret(
            client=client,
            secret_id="ai-editorial-team/prod",
            access_token="fresh-access-token",
            refresh_token="rotated-refresh-token",
        )

        self.assertEqual(client.get_calls, ["ai-editorial-team/prod"])
        self.assertEqual(len(client.put_calls), 1)
        updated_secret = json_loads(client.put_calls[0]["SecretString"])
        self.assertEqual(updated_secret["OPENAI_API_KEY"], "keep-me")
        self.assertEqual(updated_secret["X_ACCESS_TOKEN"], "fresh-access-token")
        self.assertEqual(updated_secret["X_REFRESH_TOKEN"], "rotated-refresh-token")

    def test_factory_keeps_existing_refresh_token_when_x_does_not_rotate_it(self):
        persisted = {}

        def fake_refresh(config):
            return XTokenRefreshResult(access_token="fresh-access-token")

        def fake_update(secret_id: str, access_token: str, refresh_token: str) -> None:
            persisted["secret_id"] = secret_id
            persisted["access_token"] = access_token
            persisted["refresh_token"] = refresh_token

        with patch.dict(
            os.environ,
            {
                "X_ACCESS_TOKEN": "old-access-token",
                "X_REFRESH_TOKEN": "old-refresh-token",
                "X_CLIENT_ID": "client-id",
                "X_CLIENT_SECRET": "client-secret",
            },
        ), patch(
            "ai_editorial_team.infrastructure.publishing.x_publisher."
            "_refresh_x_oauth_token",
            fake_refresh,
        ), patch(
            "ai_editorial_team.infrastructure.publishing.x_publisher."
            "_update_x_tokens_in_secrets_manager",
            fake_update,
        ):
            publisher = create_x_publisher_from_env()

        self.assertEqual(persisted["secret_id"], "ai-editorial-team/prod")
        self.assertEqual(persisted["access_token"], "fresh-access-token")
        self.assertEqual(persisted["refresh_token"], "old-refresh-token")
        self.assertEqual(
            publisher.api.config.user_access_token,
            "fresh-access-token",
        )


def _create_image_files(temp_dir: str) -> list[str]:
    image_paths = []
    for index in range(1, 4):
        image_path = Path(temp_dir) / f"rank-{index}.png"
        image_path.write_bytes(b"fake-image")
        image_paths.append(str(image_path))
    return image_paths


def _x_config() -> XPublishingConfig:
    return XPublishingConfig(
        user_access_token="old-access-token",
        refresh_token="old-refresh-token",
        client_id="client-id",
        client_secret="client-secret",
    )


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload)


def json_loads(payload: str) -> dict:
    import json

    return json.loads(payload)
