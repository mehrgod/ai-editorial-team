import tempfile
import unittest
from pathlib import Path

from ai_editorial_team.application.workflow import EditorialWorkflow
from ai_editorial_team.domain.models import Story
from ai_editorial_team.domain.ports import SocialPublisher
from ai_editorial_team.infrastructure.publishing.config import (
    InstagramPublishingConfig,
)
from ai_editorial_team.infrastructure.publishing.instagram_publisher import (
    InstagramMediaContainerError,
    InstagramPublisher,
)


class FakeResearchAgent:
    def __init__(self, story: Story) -> None:
        self._story = story

    def research(self) -> Story:
        return self._story


class FakeChiefEditor:
    def select_story(self, stories):
        return {
            "selected_story": stories[0],
            "editorial_reason": "Selected for testing.",
        }


class FakeInstagramAgent:
    def generate_caption(self, story: Story):
        return {"caption": f"Instagram for {story['headline']}"}


class FakeXAgent:
    def generate_post(self, story: Story):
        return {"post": f"X for {story['headline']}"}


class FakeImagePromptAgent:
    def generate_image_prompt(self, story: Story):
        return {"image_prompt": f"Image prompt for {story['headline']}"}


class RecordingImageGenerator:
    def generate(self, image_prompt: str):
        return {"file_path": "/tmp/editorial.png"}


class RecordingImageUrlProvider:
    def provide_url(self, generated_image):
        return {"url": "https://example.com/editorial.png"}


class RecordingSocialPublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, publication):
        self.calls.append(publication)
        return {
            "platform": "Instagram",
            "publication_id": "ig-media-123",
            "publication_url": "https://instagram.com/p/ig-media-123",
        }


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
        raise RuntimeError("network down")

    def publish_media_container(self, container_id: str) -> str:
        raise AssertionError("should not be called")

    def fetch_publication_url(self, publication_id: str) -> str:
        raise AssertionError("should not be called")


class InstagramPublishingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.story = {
            "domain": "Finance",
            "headline": "Markets climb on cooling inflation",
            "summary": "A simple test summary.",
            "reason": "A simple test reason.",
        }

    def _build_workflow(self, social_publisher):
        return EditorialWorkflow(
            finance_research_agent=FakeResearchAgent(self.story),
            ai_research_agent=FakeResearchAgent(self.story),
            sports_research_agent=FakeResearchAgent(self.story),
            chief_editor=FakeChiefEditor(),
            instagram_content_agent=FakeInstagramAgent(),
            x_content_agent=FakeXAgent(),
            image_prompt_agent=FakeImagePromptAgent(),
            image_generator=RecordingImageGenerator(),
            image_url_provider=RecordingImageUrlProvider(),
            social_publisher=social_publisher,
        )

    def test_instagram_publisher_conforms_to_social_publisher_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")

            publisher = InstagramPublisher(
                config=InstagramPublishingConfig(
                    instagram_professional_account_id="123",
                    meta_access_token="token",
                    graph_api_version="v23.0",
                ),
                api=FakeInstagramGraphApi(),
            )

            self.assertIsInstance(publisher, SocialPublisher)

    def test_media_container_and_publish_are_called_once_with_expected_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")

            api = FakeInstagramGraphApi()
            publisher = InstagramPublisher(
                config=InstagramPublishingConfig(
                    instagram_professional_account_id="123",
                    meta_access_token="token",
                    graph_api_version="v23.0",
                ),
                api=api,
            )

            result = publisher.publish(
                {
                    "caption": "A polished Instagram caption.",
                    "image_url": "https://example.com/editorial.png",
                }
            )

            self.assertEqual(api.create_calls, [
                ("A polished Instagram caption.", "https://example.com/editorial.png")
            ])
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

    def test_workflow_includes_publication_result(self):
        publisher = RecordingSocialPublisher()
        workflow = self._build_workflow(publisher)

        result = workflow.run()

        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            publisher.calls[0],
            {
                "caption": "Instagram for Markets climb on cooling inflation",
                "image_url": "https://example.com/editorial.png",
            },
        )
        self.assertEqual(
            result["publication_result"]["publication_id"],
            "ig-media-123",
        )

    def test_api_failures_produce_a_clear_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")

            publisher = InstagramPublisher(
                config=InstagramPublishingConfig(
                    instagram_professional_account_id="123",
                    meta_access_token="token",
                    graph_api_version="v23.0",
                ),
                api=ExplodingInstagramGraphApi(),
            )

            with self.assertRaises(InstagramMediaContainerError) as context:
                publisher.publish(
                    {
                        "caption": "A polished Instagram caption.",
                        "image_url": "https://example.com/editorial.png",
                    }
                )

            self.assertIn("media container creation failed", str(context.exception))
