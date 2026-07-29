from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import Story, XContent
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIXContentError(OpenAIStructuredAgentError):
    """Raised when X content generation fails."""


class XPostResponse(BaseModel):
    post: str = Field(
        description="A concise X post ready to publish.",
        max_length=280,
    )


class XContentAgent(OpenAIStructuredAgent[XPostResponse, Story, XContent]):
    """OpenAI-powered X content generator."""

    def generate_post(self, story: Story) -> XContent:
        return self.run(input_payload=_x_prompt(story), context=story)

    def instructions(self) -> str:
        return _x_instructions()

    def response_model(self) -> type[XPostResponse]:
        return XPostResponse

    def to_domain_result(self, response: XPostResponse, context: Story) -> XContent:
        return {"post": response.post}

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI X content request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return f"OpenAI X content returned invalid structured output: {exc}"

    def empty_output_message(self) -> str:
        return "OpenAI X content did not return structured output."


def _x_instructions() -> str:
    return (
        "You are an X (Twitter) content strategist for a professional "
        "editorial brand. Write concise, engaging, factual posts that explain "
        "why the story matters and encourage discussion. Stay under 280 "
        "characters. Do not include hashtags. "
        "Return only structured JSON matching the provided schema. Do not "
        "include free-form text."
    )


def _x_prompt(story: Story) -> str:
    return (
        "Generate one professional X post for this selected story.\n"
        "Keep it concise, factual, and engaging. Highlight why the story "
        "matters and invite discussion. Stay under 280 characters.\n\n"
        f"Domain: {story['domain']}\n"
        f"Headline: {story['headline']}\n"
        f"Summary: {story['summary']}\n"
        f"Reason: {story['reason']}"
    )
