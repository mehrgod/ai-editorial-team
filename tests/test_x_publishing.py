import tempfile
import unittest
from pathlib import Path

from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.x_publisher import (
    XMediaUploadError,
    XPostCreationError,
    XPublisher,
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


def _create_image_files(temp_dir: str) -> list[str]:
    image_paths = []
    for index in range(1, 4):
        image_path = Path(temp_dir) / f"rank-{index}.png"
        image_path.write_bytes(b"fake-image")
        image_paths.append(str(image_path))
    return image_paths
