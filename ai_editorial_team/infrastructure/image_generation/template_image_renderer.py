from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from ai_editorial_team.domain.models import GeneratedImage, InstagramStoryContent
from ai_editorial_team.domain.ports import TemplateImageRenderer as TemplateImageRendererPort
from ai_editorial_team.infrastructure.image_generation.openai_image_generator import (
    IMAGE_OUTPUT_DIRECTORY,
    OpenAIImageGenerationError,
)


IMAGE_SIZE = 1024
CARD_MARGIN = 72

DOMAIN_COLORS = {
    "Finance": (24, 128, 83),
    "Artificial Intelligence": (37, 99, 235),
    "Sports": (234, 88, 12),
}
DEFAULT_ACCENT_COLOR = (79, 70, 229)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class TemplateImageRenderer(TemplateImageRendererPort):
    """Renders clean local social cards for lower-ranked stories."""

    output_dir: Path = IMAGE_OUTPUT_DIRECTORY
    timestamp_factory: Callable[[], str] = _utc_timestamp

    def render(self, story_content: InstagramStoryContent) -> GeneratedImage:
        story = story_content["story"]
        rank = story_content["rank"]
        accent_color = DOMAIN_COLORS.get(story["domain"], DEFAULT_ACCENT_COLOR)

        image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (248, 250, 252))
        draw = ImageDraw.Draw(image)

        self._draw_background(draw, accent_color)
        self._draw_content(draw, story_content, accent_color)

        file_path = (
            self.output_dir
            / f"template_rank_{rank}_{self.timestamp_factory()}.png"
        )
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            image.save(file_path, format="PNG")
        except OSError as exc:
            raise OpenAIImageGenerationError(
                f"Template image renderer could not save the image to {file_path}: {exc}"
            ) from exc

        return {"file_path": str(file_path)}

    def _draw_background(self, draw: ImageDraw.ImageDraw, accent_color: tuple[int, int, int]) -> None:
        draw.rectangle((0, 0, IMAGE_SIZE, 26), fill=accent_color)
        draw.rectangle((0, IMAGE_SIZE - 26, IMAGE_SIZE, IMAGE_SIZE), fill=accent_color)
        draw.rounded_rectangle(
            (
                CARD_MARGIN,
                CARD_MARGIN,
                IMAGE_SIZE - CARD_MARGIN,
                IMAGE_SIZE - CARD_MARGIN,
            ),
            radius=28,
            fill=(255, 255, 255),
            outline=(226, 232, 240),
            width=2,
        )

    def _draw_content(
        self,
        draw: ImageDraw.ImageDraw,
        story_content: InstagramStoryContent,
        accent_color: tuple[int, int, int],
    ) -> None:
        story = story_content["story"]
        rank = story_content["rank"]
        left = CARD_MARGIN + 58
        right = IMAGE_SIZE - CARD_MARGIN - 58
        y = CARD_MARGIN + 58

        rank_font = _font(34, bold=True)
        label_font = _font(30, bold=True)
        headline_font = _font(58, bold=True)
        summary_font = _font(34)
        footer_font = _font(26)

        rank_label = f"RANK {rank}"
        rank_width = _text_width(draw, rank_label, rank_font)
        draw.rounded_rectangle(
            (left, y, left + rank_width + 42, y + 58),
            radius=24,
            fill=accent_color,
        )
        draw.text((left + 21, y + 11), rank_label, fill=(255, 255, 255), font=rank_font)

        domain = story["domain"].upper()
        draw.text((left, y + 92), domain, fill=accent_color, font=label_font)

        y += 160
        headline_lines = _wrap_text(draw, story["headline"], headline_font, right - left)
        for line in headline_lines[:5]:
            draw.text((left, y), line, fill=(15, 23, 42), font=headline_font)
            y += 66

        y += 22
        summary = shorten(story["summary"], width=210, placeholder="...")
        summary_lines = _wrap_text(draw, summary, summary_font, right - left)
        for line in summary_lines[:6]:
            draw.text((left, y), line, fill=(51, 65, 85), font=summary_font)
            y += 46

        draw.line(
            (left, IMAGE_SIZE - CARD_MARGIN - 110, right, IMAGE_SIZE - CARD_MARGIN - 110),
            fill=(203, 213, 225),
            width=2,
        )
        draw.text(
            (left, IMAGE_SIZE - CARD_MARGIN - 80),
            "AI Editorial Team",
            fill=(100, 116, 139),
            font=footer_font,
        )


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current_line = ""

    for word in text.split():
        candidate = f"{current_line} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width:
            current_line = candidate
            continue

        if current_line:
            lines.append(current_line)
        current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left
