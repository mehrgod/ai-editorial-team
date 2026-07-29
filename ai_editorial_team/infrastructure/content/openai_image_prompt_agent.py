from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import ImagePrompt, Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIImagePromptError(OpenAIStructuredAgentError):
    """Raised when image prompt generation fails."""


class ImagePromptResponse(BaseModel):
    image_prompt: str = Field(
        description="A detailed square social-media image prompt."
    )


class ImagePromptAgent(OpenAIStructuredAgent[ImagePromptResponse, Story, ImagePrompt]):
    """OpenAI-powered image prompt generator."""

    def generate_image_prompt(self, story: Story) -> ImagePrompt:
        return self.run(input_payload=_image_prompt(story), context=story)

    def instructions(self) -> str:
        return _image_prompt_instructions()

    def response_model(self) -> type[ImagePromptResponse]:
        return ImagePromptResponse

    def to_domain_result(
        self, response: ImagePromptResponse, context: Story
    ) -> ImagePrompt:
        return {"image_prompt": response.image_prompt}

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI image prompt request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return f"OpenAI image prompt returned invalid structured output: {exc}"

    def empty_output_message(self) -> str:
        return "OpenAI image prompt did not return structured output."


def _image_prompt_instructions() -> str:
    return (
        "You are an art director generating prompts for a future image "
        "generation model. Write one detailed prompt for a square "
        "social-media image that clearly describes the main visual subject, "
        "reflects the selected story accurately, specifies composition and "
        "visual hierarchy, suggests lighting, mood, and environment, and "
        "includes the domain's visual identity when appropriate: green accents "
        "for Finance, blue accents for Artificial Intelligence, orange "
        "accents for Sports. Avoid visible text, captions, logos, watermarks, "
        "brand marks, and unsupported factual details. Return only structured "
        "JSON matching the provided schema. Do not include free-form text."
    )


def _image_prompt(story: Story) -> str:
    domain_identity = _domain_visual_identity(story["domain"])
    return (
        "Generate one professional image prompt for this selected story.\n"
        "The prompt must be suitable for a square social-media image. Clearly "
        "describe the main visual subject, composition, visual hierarchy, "
        "lighting, mood, and environment. Avoid visible text, captions, logos, "
        "watermarks, brand marks, and unsupported factual details.\n\n"
        f"Domain: {story['domain']}\n"
        f"Headline: {story['headline']}\n"
        f"Summary: {story['summary']}\n"
        f"Reason: {story['reason']}\n"
        f"Visual Identity: {domain_identity}"
    )


def _domain_visual_identity(domain: str) -> str:
    if domain == "Finance":
        return "Use green accents to signal markets and financial analysis."
    if domain == "Artificial Intelligence":
        return "Use blue accents to signal technology and intelligence."
    if domain == "Sports":
        return "Use orange accents to signal energy, action, and competition."
    return "Use a clean, editorial visual style appropriate to the story."
