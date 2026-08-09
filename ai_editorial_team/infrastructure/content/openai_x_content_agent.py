from typing import List

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import RankedStory, XContent
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIXContentError(OpenAIStructuredAgentError):
    """Raised when X content generation fails."""


class XPostResponse(BaseModel):
    post: str = Field(
        description="A concise X post ready to publish.",
        max_length=250,
    )


class XContentAgent(
    OpenAIStructuredAgent[XPostResponse, List[RankedStory], XContent]
):
    """OpenAI-powered X content generator."""

    def generate_post(self, ranked_stories: List[RankedStory]) -> XContent:
        return self.run(
            input_payload=_x_prompt(ranked_stories),
            context=ranked_stories,
        )

    def instructions(self) -> str:
        return _x_instructions()

    def response_model(self) -> type[XPostResponse]:
        return XPostResponse

    def to_domain_result(
        self, response: XPostResponse, context: List[RankedStory]
    ) -> XContent:
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
        "editorial brand. Write one concise, engaging, factual post covering "
        "all 3 ranked stories in rank order. Clearly map the text to the "
        "image order using a compact structure such as 1/, 2/, 3/. Stay under "
        "250 characters. Do not use unnecessary hashtags. Do not use long "
        "introductions or conclusions. "
        "Return only structured JSON matching the provided schema. Do not "
        "include free-form text."
    )


def _x_prompt(ranked_stories: List[RankedStory]) -> str:
    return (
        "Generate one compact X post covering all 3 ranked stories below.\n"
        "Requirements:\n"
        "- Include all 3 stories.\n"
        "- Preserve rank order.\n"
        "- Clearly map text to the image order.\n"
        "- Stay under 250 characters.\n"
        "- Do not use unnecessary hashtags.\n"
        "- Do not use long introductions or conclusions.\n\n"
        f"{_format_ranked_stories(ranked_stories)}"
    )


def _format_ranked_stories(ranked_stories: List[RankedStory]) -> str:
    return "\n\n".join(
        (
            f"Rank {ranked_story['rank']}:\n"
            f"Domain: {ranked_story['story']['domain']}\n"
            f"Headline: {ranked_story['story']['headline']}\n"
            f"Summary: {ranked_story['story']['summary']}\n"
            f"Editorial Reason: {ranked_story['editorial_reason']}"
        )
        for ranked_story in ranked_stories
    )
