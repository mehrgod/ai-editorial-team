from pathlib import Path
from urllib.parse import quote

from ai_editorial_team.domain.models import GeneratedImage, PublicImageUrl
from ai_editorial_team.domain.ports import ImageUrlProvider


MOCK_PUBLIC_IMAGE_BASE_URL = "https://example.com/generated-images"


class ImageUrlProviderError(RuntimeError):
    """Raised when a public URL cannot be produced for a local image."""


class MockImageUrlProvider(ImageUrlProvider):
    """Temporary stand-in for future public image storage."""

    def provide_url(self, generated_image: GeneratedImage) -> PublicImageUrl:
        image_path = Path(generated_image["file_path"])
        if not image_path.is_file():
            raise ImageUrlProviderError(
                f"Generated image file was not found: {image_path}"
            )

        return {
            "url": f"{MOCK_PUBLIC_IMAGE_BASE_URL}/{quote(image_path.name)}"
        }
