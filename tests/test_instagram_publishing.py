import unittest

from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.instagram_publisher import (
    InstagramMediaContainerError,
    InstagramPublisher,
)


class FakeInstagramGraphApi:
    def __init__(self) -> None:
        self.create_calls = []
        self.publish_calls = []
        self.lookup_calls = []

    def create_media_container(self, caption: str, image_url: str) -> str:
        self.create_calls.append((caption, image_url))
        return "container-123"

    def publish_media_container(self, container_id: str) -> str:
        self.publish_calls.append(container_id)
        return "publication-456"

    def fetch_publication_url(self, publication_id: str) -> str:
        self.lookup_calls.append(publication_id)
        return "https://instagram.com/p/publication-456"


class ExplodingInstagramGraphApi:
    def create_media_container(self, caption: str, image_url: str) -> str:
        raise InstagramMediaContainerError("container failed")

    def publish_media_container(self, container_id: str) -> str:
        raise AssertionError("should not be called")

    def fetch_publication_url(self, publication_id: str) -> str:
        raise AssertionError("should not be called")


class InstagramPublishingTests(unittest.TestCase):
    def test_instagram_publisher_conforms_to_social_publisher_port(self):
        publisher = InstagramPublisher(api=FakeInstagramGraphApi())

        self.assertIsInstance(publisher, SocialPublisher)

    def test_publisher_sends_caption_and_presigned_image_url(self):
        api = FakeInstagramGraphApi()
        publisher = InstagramPublisher(api=api)

        result = publisher.publish(
            {
                "caption": "A polished Instagram caption.",
                "image_url": "https://example.com/presigned-image.png",
            }
        )

        self.assertEqual(
            api.create_calls,
            [
                (
                    "A polished Instagram caption.",
                    "https://example.com/presigned-image.png",
                )
            ],
        )
        self.assertEqual(api.publish_calls, ["container-123"])
        self.assertEqual(api.lookup_calls, ["publication-456"])
        self.assertEqual(
            result,
            {
                "platform": "Instagram",
                "publication_id": "publication-456",
                "publication_url": "https://instagram.com/p/publication-456",
            },
        )

    def test_api_failures_produce_clear_infrastructure_error(self):
        publisher = InstagramPublisher(api=ExplodingInstagramGraphApi())

        with self.assertRaises(InstagramMediaContainerError) as context:
            publisher.publish(
                {
                    "caption": "A polished Instagram caption.",
                    "image_url": "https://example.com/presigned-image.png",
                }
            )

        self.assertIn("media container creation failed", str(context.exception))
