import tempfile
import unittest
from pathlib import Path

from ai_editorial_team.application.workflow import EditorialWorkflow
from ai_editorial_team.domain.models import Story
from ai_editorial_team.infrastructure.image_generation.openai_image_generator import (
    OpenAIImageGenerator,
    save_image_bytes,
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
    def __init__(self) -> None:
        self.prompts = []

    def generate(self, image_prompt: str):
        self.prompts.append(image_prompt)
        return {"file_path": "/tmp/editorial.png"}


class RecordingImageStorage:
    def __init__(self) -> None:
        self.local_file_paths = []

    def store(self, local_file_path: str):
        self.local_file_paths.append(local_file_path)
        return {
            "object_key": "images/editorial.png",
            "public_url": "https://example.com/presigned-editorial.png",
        }


class RecordingInstagramPublisher:
    def __init__(self) -> None:
        self.publications = []

    def publish(self, publication):
        self.publications.append(publication)
        return {
            "platform": "Instagram",
            "publication_id": "ig-media-123",
            "publication_url": "https://instagram.com/p/ig-media-123",
        }


class RecordingXPublisher:
    def __init__(self) -> None:
        self.publications = []

    def publish(self, publication):
        self.publications.append(publication)
        return {
            "platform": "X",
            "publication_id": "x-post-123",
            "publication_url": "https://x.com/i/web/status/x-post-123",
        }


class EditorialImageGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.story = {
            "domain": "Finance",
            "headline": "Markets climb on cooling inflation",
            "summary": "A simple test summary.",
            "reason": "A simple test reason.",
        }

    def _build_workflow(
        self,
        image_generator,
        image_storage=None,
        instagram_publisher=None,
        x_publisher=None,
    ):
        return EditorialWorkflow(
            finance_research_agent=FakeResearchAgent(self.story),
            ai_research_agent=FakeResearchAgent(self.story),
            sports_research_agent=FakeResearchAgent(self.story),
            chief_editor=FakeChiefEditor(),
            instagram_content_agent=FakeInstagramAgent(),
            x_content_agent=FakeXAgent(),
            image_prompt_agent=FakeImagePromptAgent(),
            image_generator=image_generator,
            image_storage=image_storage or RecordingImageStorage(),
            instagram_publisher=instagram_publisher or RecordingInstagramPublisher(),
            x_publisher=x_publisher or RecordingXPublisher(),
        )

    def test_image_generator_receives_prompt_once_and_final_package_contains_path(self):
        image_generator = RecordingImageGenerator()
        workflow = self._build_workflow(image_generator)

        result = workflow.run()

        self.assertEqual(
            image_generator.prompts,
            ["Image prompt for Markets climb on cooling inflation"],
        )
        self.assertEqual(result["generated_image"]["file_path"], "/tmp/editorial.png")

    def test_local_file_path_is_passed_to_storage_and_final_package_contains_result(self):
        image_generator = RecordingImageGenerator()
        image_storage = RecordingImageStorage()
        workflow = self._build_workflow(image_generator, image_storage)

        result = workflow.run()

        self.assertEqual(image_storage.local_file_paths, ["/tmp/editorial.png"])
        self.assertEqual(result["stored_image"]["object_key"], "images/editorial.png")
        self.assertEqual(
            result["stored_image"]["public_url"],
            "https://example.com/presigned-editorial.png",
        )

    def test_s3_presigned_url_is_passed_to_instagram_publisher(self):
        image_generator = RecordingImageGenerator()
        instagram_publisher = RecordingInstagramPublisher()
        workflow = self._build_workflow(
            image_generator,
            instagram_publisher=instagram_publisher,
        )

        result = workflow.run()

        self.assertEqual(
            instagram_publisher.publications,
            [
                {
                    "caption": "Instagram for Markets climb on cooling inflation",
                    "image_url": "https://example.com/presigned-editorial.png",
                }
            ],
        )
        self.assertEqual(
            result["instagram_publication_result"]["publication_id"],
            "ig-media-123",
        )

    def test_generated_x_post_is_passed_to_x_publisher(self):
        image_generator = RecordingImageGenerator()
        x_publisher = RecordingXPublisher()
        workflow = self._build_workflow(
            image_generator,
            x_publisher=x_publisher,
        )

        result = workflow.run()

        self.assertEqual(
            x_publisher.publications,
            [{"text": "X for Markets climb on cooling inflation"}],
        )
        self.assertEqual(
            result["x_publication_result"]["publication_id"],
            "x-post-123",
        )

    def test_image_file_writing_logic_can_be_tested_without_real_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            file_path = save_image_bytes(
                output_dir,
                b"fake-png-bytes",
                "20260729T120000000000Z",
            )

            self.assertEqual(
                file_path,
                output_dir / "editorial_20260729T120000000000Z.png",
            )
            self.assertEqual(file_path.read_bytes(), b"fake-png-bytes")


class OpenAIImageGeneratorTests(unittest.TestCase):
    def test_openai_image_generator_uses_timestamp_factory(self):
        class FakeImage:
            b64_json = "ZmFrZS1pbWFnZQ=="

        class FakeResponse:
            data = [FakeImage()]

        class FakeImages:
            def __init__(self):
                self.calls = []

            def generate(self, **kwargs):
                self.calls.append(kwargs)
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.images = FakeImages()

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = OpenAIImageGenerator(
                client=FakeClient(),
                model="gpt-image-1",
                output_dir=Path(temp_dir),
                timestamp_factory=lambda: "20260729T120000000000Z",
            )

            result = generator.generate("A square editorial illustration")

            self.assertEqual(
                result["file_path"],
                str(Path(temp_dir) / "editorial_20260729T120000000000Z.png"),
            )
