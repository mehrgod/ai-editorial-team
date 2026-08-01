import binascii
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from openai import OpenAI, OpenAIError

from ai_editorial_team.domain.models import GeneratedImage
from ai_editorial_team.domain.ports import ImageGenerator
from ai_editorial_team.infrastructure.openai.config import OpenAIInfrastructureError


IMAGE_OUTPUT_DIRECTORY = Path("output/images")


class OpenAIImageGenerationError(OpenAIInfrastructureError):
    """Raised when OpenAI image generation fails."""


def save_image_bytes(output_dir: Path, image_bytes: bytes, timestamp: str) -> Path:
    file_path = output_dir / f"editorial_{timestamp}.png"

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(image_bytes)
    except OSError as exc:
        raise OpenAIImageGenerationError(
            f"OpenAI image generation could not save the image to {file_path}: {exc}"
        ) from exc

    return file_path


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class OpenAIImageGenerator(ImageGenerator):
    """OpenAI-powered image generator that saves images locally."""

    client: OpenAI
    model: str
    output_dir: Path = IMAGE_OUTPUT_DIRECTORY
    timestamp_factory: Callable[[], str] = _utc_timestamp

    def generate(self, image_prompt: str) -> GeneratedImage:
        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=image_prompt,
                size="1024x1024",
                output_format="png",
            )
        except OpenAIError as exc:
            raise OpenAIImageGenerationError(
                f"OpenAI image generation request failed: {exc}"
            ) from exc

        image_bytes = _extract_image_bytes(response)

        file_path = save_image_bytes(
            self.output_dir,
            image_bytes,
            self.timestamp_factory(),
        )
        return {"file_path": str(file_path)}


def _extract_image_bytes(response) -> bytes:
    if not response.data:
        raise OpenAIImageGenerationError(
            "OpenAI image generation did not return any image data."
        )

    image = response.data[0]
    if not image.b64_json:
        raise OpenAIImageGenerationError(
            "OpenAI image generation did not return image bytes."
        )

    try:
        return b64decode(image.b64_json)
    except (binascii.Error, ValueError) as exc:
        raise OpenAIImageGenerationError(
            "OpenAI image generation returned invalid image data."
        ) from exc
