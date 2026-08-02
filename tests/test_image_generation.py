import tempfile
import unittest
from pathlib import Path

from ai_editorial_team.infrastructure.image_generation.openai_image_generator import (
    OpenAIImageGenerator,
    save_image_bytes,
)


class EditorialImageGenerationTests(unittest.TestCase):
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
