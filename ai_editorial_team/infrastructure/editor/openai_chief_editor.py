import json
from typing import List

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import EditorialDecision, Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIChiefEditorError(OpenAIStructuredAgentError):
    """Raised when the LLM Chief Editor cannot produce a decision."""


class EditorialSelectionResponse(BaseModel):
    selected_story_id: str = Field(
        description="The id of exactly one selected candidate story."
    )
    editorial_reason: str = Field(
        description="A concise explanation of why this story was selected."
    )


class LLMChiefEditor(
    OpenAIStructuredAgent[EditorialSelectionResponse, List[Story], EditorialDecision]
):
    """OpenAI-powered Chief Editor that implements the domain ChiefEditor port."""

    def select_story(self, stories: List[Story]) -> EditorialDecision:
        if not stories:
            raise OpenAIChiefEditorError(
                "LLM Chief Editor requires at least one candidate story."
            )

        return self.run(
            input_payload=_editor_prompt(_build_story_options(stories)),
            context=stories,
        )

    def instructions(self) -> str:
        return _editor_instructions()

    def response_model(self) -> type[EditorialSelectionResponse]:
        return EditorialSelectionResponse

    def to_domain_result(
        self, response: EditorialSelectionResponse, context: List[Story]
    ) -> EditorialDecision:
        selected_story = _find_selected_story(context, response.selected_story_id)
        return {
            "selected_story": selected_story,
            "editorial_reason": response.editorial_reason,
        }

    def error_message(self, exc: OpenAIError) -> str:
        return f"OpenAI Chief Editor request failed: {exc}"

    def validation_error_message(self, exc: ValidationError) -> str:
        return f"OpenAI Chief Editor returned invalid structured output: {exc}"

    def empty_output_message(self) -> str:
        return "OpenAI Chief Editor did not return structured output."


def _build_story_options(stories: List[Story]) -> List[dict]:
    return [
        {
            "id": _story_id(index),
            "domain": story["domain"],
            "headline": story["headline"],
            "summary": story["summary"],
            "reason": story["reason"],
        }
        for index, story in enumerate(stories)
    ]


def _editor_prompt(story_options: List[dict]) -> str:
    return (
        "Select exactly one candidate story from this JSON array:\n"
        f"{json.dumps(story_options, indent=2)}\n"
        "The selected_story_id must match exactly one provided id."
    )


def _editor_instructions() -> str:
    return (
        "You are the Chief Editor for an AI-powered editorial team. "
        "Evaluate the candidate stories and select the single best story for "
        "today's audience. Consider newsworthiness, broad audience appeal, "
        "timeliness, potential engagement, and clarity. Return only structured "
        "JSON matching the provided schema. Do not include free-form text."
    )


def _find_selected_story(
    stories: List[Story], selected_story_id: str
) -> Story:
    for index, story in enumerate(stories):
        if _story_id(index) == selected_story_id:
            return story

    valid_ids = ", ".join(_story_id(index) for index in range(len(stories)))
    raise OpenAIChiefEditorError(
        "OpenAI Chief Editor selected an unknown story id "
        f"'{selected_story_id}'. Expected one of: {valid_ids}."
    )


def _story_id(index: int) -> str:
    return f"story_{index + 1}"
