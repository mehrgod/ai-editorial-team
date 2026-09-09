from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import NewsworthinessDecision, Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIStoryNewsworthinessError(OpenAIStructuredAgentError):
    """Raised when story newsworthiness assessment fails."""


class StoryNewsworthinessResponse(BaseModel):
    is_newsworthy: bool = Field(
        description="Whether the candidate is a timely news story."
    )
    reason: str = Field(
        description="Brief explanation for accepting or rejecting the story.",
        min_length=1,
        max_length=240,
    )


class StoryNewsworthinessAgent(
    OpenAIStructuredAgent[
        StoryNewsworthinessResponse,
        Story,
        NewsworthinessDecision,
    ]
):
    """OpenAI-powered assessor for RSS story candidates."""

    def assess_story(self, story: Story) -> NewsworthinessDecision:
        return self.run(input_payload=_newsworthiness_prompt(story), context=story)

    def instructions(self) -> str:
        return _newsworthiness_instructions()

    def response_model(self) -> type[StoryNewsworthinessResponse]:
        return StoryNewsworthinessResponse

    def to_domain_result(
        self, response: StoryNewsworthinessResponse, context: Story
    ) -> NewsworthinessDecision:
        return {
            "is_newsworthy": response.is_newsworthy,
            "reason": response.reason.strip(),
        }

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI story newsworthiness request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return (
            "OpenAI story newsworthiness returned invalid structured output: " f"{exc}"
        )

    def empty_output_message(self) -> str:
        return "OpenAI story newsworthiness did not return structured output."


def _newsworthiness_instructions() -> str:
    return (
        "You are a newsworthiness editor for an automated editorial workflow. "
        "Accept timely news stories about concrete recent events, decisions, "
        "announcements, results, injuries, market moves, product releases, or "
        "public developments. Reject evergreen pages, guides, rankings hubs, "
        "mock drafts, projections, betting pages, fantasy tools, previews, and "
        "generic analysis pages unless they are clearly tied to a specific "
        "current event. Return only structured JSON matching the provided "
        "schema. Do not include free-form text."
    )


def _newsworthiness_prompt(story: Story) -> str:
    return (
        "Assess whether this RSS candidate should be used as a timely news "
        "story for today's editorial package.\n\n"
        f"Domain: {story['domain']}\n"
        f"Headline: {story['headline']}\n"
        f"Summary: {story['summary']}\n"
        f"Source Context: {story['reason']}"
    )
