from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIStorySummaryError(OpenAIStructuredAgentError):
    """Raised when story summary generation fails."""


class StorySummaryResponse(BaseModel):
    summary: str = Field(
        description="A concise editorial summary for the story.",
        min_length=1,
        max_length=280,
    )


class StorySummaryAgent(OpenAIStructuredAgent[StorySummaryResponse, Story, str]):
    """OpenAI-powered summary writer for RSS stories missing summaries."""

    def summarize_story(self, story: Story) -> str:
        return self.run(input_payload=_summary_prompt(story), context=story)

    def instructions(self) -> str:
        return _summary_instructions()

    def response_model(self) -> type[StorySummaryResponse]:
        return StorySummaryResponse

    def to_domain_result(self, response: StorySummaryResponse, context: Story) -> str:
        summary = response.summary.strip()
        if summary.lower() in {"null", "none", "n/a"}:
            raise OpenAIStorySummaryError(
                "OpenAI story summary returned a placeholder instead of a summary."
            )
        return summary

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI story summary request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return "OpenAI story summary returned invalid structured output: " f"{exc}"

    def empty_output_message(self) -> str:
        return "OpenAI story summary did not return structured output."


def _summary_instructions() -> str:
    return (
        "You are an editorial summarization agent. Write one concise, factual "
        "summary for a news story when an RSS feed does not provide one. Use "
        "only the supplied domain, headline, and source context. Do not invent "
        "specific details beyond what is supported by the supplied text. Return "
        "only structured JSON matching the provided schema. Do not include "
        "free-form text."
    )


def _summary_prompt(story: Story) -> str:
    return (
        "Generate one concise editorial summary for this story.\n"
        "Requirements:\n"
        "- One sentence.\n"
        "- 280 characters or fewer.\n"
        "- Useful for captions and social image text.\n"
        "- Do not mention that the RSS feed was missing a summary.\n\n"
        f"Domain: {story['domain']}\n"
        f"Headline: {story['headline']}\n"
        f"Source Context: {story['reason']}"
    )
