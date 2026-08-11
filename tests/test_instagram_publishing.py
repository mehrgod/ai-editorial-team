import unittest

from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.instagram_publisher import (
    InstagramMediaContainerError,
    InstagramPublishingError,
    InstagramPublisher,
)


class FakeInstagramGraphApi:
    def __init__(self) -> None:
        self.child_create_calls = []
        self.parent_create_calls = []
        self.status_calls = []
        self.publish_calls = []
        self.lookup_calls = []

    def create_carousel_item_container(self, image_url: str) -> str:
        self.child_create_calls.append(image_url)
        return f"child-{len(self.child_create_calls)}"

    def create_carousel_container(
        self, caption: str, child_container_ids: list[str]
    ) -> str:
        self.parent_create_calls.append((caption, child_container_ids))
        return "parent-123"

    def fetch_container_status(self, container_id: str) -> str:
        self.status_calls.append(container_id)
        return "FINISHED"

    def publish_media_container(self, container_id: str) -> str:
        self.publish_calls.append(container_id)
        return "publication-456"

    def fetch_publication_url(self, publication_id: str) -> str:
        self.lookup_calls.append(publication_id)
        return "https://instagram.com/p/publication-456"


class ExplodingInstagramGraphApi:
    def create_carousel_item_container(self, image_url: str) -> str:
        raise InstagramMediaContainerError("container failed")

    def create_carousel_container(
        self, caption: str, child_container_ids: list[str]
    ) -> str:
        raise AssertionError("should not be called")

    def publish_media_container(self, container_id: str) -> str:
        raise AssertionError("should not be called")

    def fetch_container_status(self, container_id: str) -> str:
        raise AssertionError("should not be called")

    def fetch_publication_url(self, publication_id: str) -> str:
        raise AssertionError("should not be called")


class SlowInstagramGraphApi(FakeInstagramGraphApi):
    def __init__(self) -> None:
        super().__init__()
        self._status_by_container = {
            "child-1": ["IN_PROGRESS", "FINISHED"],
            "child-2": ["FINISHED"],
            "child-3": ["FINISHED"],
            "parent-123": ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"],
        }

    def fetch_container_status(self, container_id: str) -> str:
        self.status_calls.append(container_id)
        statuses = self._status_by_container[container_id]
        if len(statuses) > 1:
            return statuses.pop(0)
        return statuses[0]


class PublishRaceInstagramGraphApi(FakeInstagramGraphApi):
    def publish_media_container(self, container_id: str) -> str:
        self.publish_calls.append(container_id)
        if len(self.publish_calls) == 1:
            raise InstagramPublishingError(
                "Instagram Graph API request failed (400): Media ID is not available"
            )
        return "publication-456"


class InstagramPublishingTests(unittest.TestCase):
    def test_instagram_publisher_conforms_to_social_publisher_port(self):
        publisher = InstagramPublisher(api=FakeInstagramGraphApi())

        self.assertIsInstance(publisher, SocialPublisher)

    def test_publisher_creates_carousel_children_parent_and_publishes_once(self):
        api = FakeInstagramGraphApi()
        publisher = InstagramPublisher(api=api)

        result = publisher.publish(
            {
                "caption": "A polished Instagram caption.",
                "image_urls": [
                    "https://example.com/rank-1.png",
                    "https://example.com/rank-2.png",
                    "https://example.com/rank-3.png",
                ],
            }
        )

        self.assertEqual(
            api.child_create_calls,
            [
                "https://example.com/rank-1.png",
                "https://example.com/rank-2.png",
                "https://example.com/rank-3.png",
            ],
        )
        self.assertEqual(
            api.parent_create_calls,
            [
                (
                    "A polished Instagram caption.",
                    ["child-1", "child-2", "child-3"],
                )
            ],
        )
        self.assertEqual(
            api.status_calls,
            ["child-1", "child-2", "child-3", "parent-123"],
        )
        self.assertEqual(api.publish_calls, ["parent-123"])
        self.assertEqual(api.lookup_calls, ["publication-456"])
        self.assertEqual(
            result,
            {
                "platform": "Instagram",
                "publication_id": "publication-456",
                "publication_url": "https://instagram.com/p/publication-456",
            },
        )

    def test_publisher_waits_until_child_and_parent_containers_are_finished(self):
        api = SlowInstagramGraphApi()
        publisher = InstagramPublisher(api=api, status_delay_seconds=0)

        publisher.publish(
            {
                "caption": "A polished Instagram caption.",
                "image_urls": [
                    "https://example.com/rank-1.png",
                    "https://example.com/rank-2.png",
                    "https://example.com/rank-3.png",
                ],
            }
        )

        self.assertEqual(
            api.status_calls,
            [
                "child-1",
                "child-1",
                "child-2",
                "child-3",
                "parent-123",
                "parent-123",
                "parent-123",
            ],
        )
        self.assertEqual(api.publish_calls, ["parent-123"])

    def test_media_id_not_available_publish_error_is_retried_once(self):
        api = PublishRaceInstagramGraphApi()
        publisher = InstagramPublisher(api=api)

        with unittest.mock.patch(
            "ai_editorial_team.infrastructure.publishing.instagram_publisher."
            "time.sleep"
        ):
            result = publisher.publish(
                {
                    "caption": "A polished Instagram caption.",
                    "image_urls": [
                        "https://example.com/rank-1.png",
                        "https://example.com/rank-2.png",
                        "https://example.com/rank-3.png",
                    ],
                }
            )

        self.assertEqual(api.publish_calls, ["parent-123", "parent-123"])
        self.assertEqual(result["publication_id"], "publication-456")

    def test_api_failures_produce_clear_infrastructure_error(self):
        publisher = InstagramPublisher(api=ExplodingInstagramGraphApi())

        with self.assertRaises(InstagramMediaContainerError) as context:
            publisher.publish(
                {
                    "caption": "A polished Instagram caption.",
                    "image_urls": [
                        "https://example.com/rank-1.png",
                        "https://example.com/rank-2.png",
                        "https://example.com/rank-3.png",
                    ],
                }
            )

        self.assertIn(
            "carousel item container creation failed",
            str(context.exception),
        )
