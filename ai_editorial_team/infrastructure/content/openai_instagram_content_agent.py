from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import InstagramContent, Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIInstagramContentError(OpenAIStructuredAgentError):
    """Raised when Instagram content generation fails."""


class InstagramCaptionResponse(BaseModel):
    caption: str = Field(
        description="A polished Instagram caption ready to publish."
    )


class InstagramContentAgent(
    OpenAIStructuredAgent[InstagramCaptionResponse, Story, InstagramContent]
):
    """OpenAI-powered Instagram content generator."""

    def generate_caption(self, story: Story) -> InstagramContent:
        return self.run(input_payload=_instagram_prompt(story), context=story)

    def instructions(self) -> str:
        return _instagram_instructions()

    def response_model(self) -> type[InstagramCaptionResponse]:
        return InstagramCaptionResponse

    def to_domain_result(
        self, response: InstagramCaptionResponse, context: Story
    ) -> InstagramContent:
        return {"caption": response.caption}

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI Instagram content request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return (
            "OpenAI Instagram content returned invalid structured output: "
            f"{exc}"
        )

    def empty_output_message(self) -> str:
        return "OpenAI Instagram content did not return structured output."


def _instagram_instructions() -> str:
    return (
        "You are an Instagram content strategist for a professional editorial "
        "brand. Write concise, clear, credible captions that make important "
        "stories accessible to a broad audience. Return only structured JSON "
        "matching the provided schema. Do not include free-form text."
    )


def _instagram_prompt(story: Story) -> str:
    return (
        "Generate one professional Instagram caption for this selected story.\n"
        "Keep it polished and readable. Make the opening line engaging, explain "
        "why the story matters, and include a tasteful call to discussion.\n\n"
        f"Domain: {story['domain']}\n"
        f"Headline: {story['headline']}\n"
        f"Summary: {story['summary']}\n"
        f"Reason: {story['reason']}"
    )
