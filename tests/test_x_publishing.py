import unittest

from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.x_publisher import (
    XPostCreationError,
    XPublisher,
)


class FakeXApi:
    def __init__(self) -> None:
        self.create_calls = []

    def create_post(self, text: str) -> str:
        self.create_calls.append(text)
        return "1234567890"


class ExplodingXApi:
    def create_post(self, text: str) -> str:
        raise XPostCreationError("post failed")


class XPublishingTests(unittest.TestCase):
    def test_x_publisher_conforms_to_social_publisher_port(self):
        publisher = XPublisher(api=FakeXApi())

        self.assertIsInstance(publisher, SocialPublisher)

    def test_generated_x_post_text_is_sent_once(self):
        api = FakeXApi()
        publisher = XPublisher(api=api)

        result = publisher.publish({"text": "A concise X post."})

        self.assertEqual(api.create_calls, ["A concise X post."])
        self.assertEqual(
            result,
            {
                "platform": "X",
                "publication_id": "1234567890",
                "publication_url": "https://x.com/i/web/status/1234567890",
            },
        )

    def test_x_api_failures_produce_clear_infrastructure_error(self):
        publisher = XPublisher(api=ExplodingXApi())

        with self.assertRaises(XPostCreationError) as context:
            publisher.publish({"text": "A concise X post."})

        self.assertIn("X post creation failed", str(context.exception))
