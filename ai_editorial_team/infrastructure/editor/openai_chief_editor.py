import json
from typing import List

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import RankedStory, Story
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
    OpenAIStructuredAgentError,
)


class OpenAIChiefEditorError(OpenAIStructuredAgentError):
    """Raised when the LLM Chief Editor cannot produce a decision."""


class RankedStoryResponse(BaseModel):
    rank: int = Field(
        description="The story rank, where 1 is most important.",
        ge=1,
        le=3,
    )
    story_id: str = Field(description="The id of exactly one candidate story.")
    editorial_reason: str = Field(
        description="A concise explanation of why this story received this rank."
    )


class EditorialRankingResponse(BaseModel):
    ranked_stories: List[RankedStoryResponse] = Field(
        description="Exactly three ranked candidate stories.",
        min_length=3,
        max_length=3,
    )


class LLMChiefEditor(
    OpenAIStructuredAgent[EditorialRankingResponse, List[Story], List[RankedStory]]
):
    """OpenAI-powered Chief Editor that implements the domain ChiefEditor port."""

    def rank_stories(self, stories: List[Story]) -> List[RankedStory]:
        if len(stories) != 3:
            raise OpenAIChiefEditorError(
                "LLM Chief Editor requires exactly three candidate stories."
            )

        return self.run(
            input_payload=_editor_prompt(_build_story_options(stories)),
            context=stories,
        )

    def instructions(self) -> str:
        return _editor_instructions()

    def response_model(self) -> type[EditorialRankingResponse]:
        return EditorialRankingResponse

    def to_domain_result(
        self, response: EditorialRankingResponse, context: List[Story]
    ) -> List[RankedStory]:
        _validate_ranking_response(response, context)
        return [
            {
                "rank": ranked_story.rank,
                "story": _find_story(context, ranked_story.story_id),
                "editorial_reason": ranked_story.editorial_reason,
            }
            for ranked_story in sorted(
                response.ranked_stories, key=lambda item: item.rank
            )
        ]

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
        "Rank every candidate story from this JSON array:\n"
        f"{json.dumps(story_options, indent=2)}\n"
        "Return exactly three ranked items. Ranks must be 1, 2, and 3. "
        "Each story_id must match exactly one provided id, and every provided "
        "story id must appear exactly once."
    )


def _editor_instructions() -> str:
    return (
        "You are the Chief Editor for an AI-powered editorial team. "
        "Evaluate the candidate stories and rank all three from most important "
        "to least important for today's audience. Consider importance, "
        "timeliness, broad audience relevance, potential impact, and editorial "
        "interest. Do not drop any story. Return only structured JSON matching "
        "the provided schema. Do not include free-form text."
    )


def _validate_ranking_response(
    response: EditorialRankingResponse, stories: List[Story]
) -> None:
    expected_ranks = {1, 2, 3}
    actual_ranks = {ranked_story.rank for ranked_story in response.ranked_stories}
    if actual_ranks != expected_ranks:
        raise OpenAIChiefEditorError(
            "OpenAI Chief Editor must return ranks 1, 2, and 3 exactly once."
        )

    expected_story_ids = {
        _story_id(index) for index in range(len(stories))
    }
    actual_story_ids = {
        ranked_story.story_id for ranked_story in response.ranked_stories
    }
    if actual_story_ids != expected_story_ids:
        valid_ids = ", ".join(sorted(expected_story_ids))
        raise OpenAIChiefEditorError(
            "OpenAI Chief Editor must rank every story exactly once. "
            f"Expected story ids: {valid_ids}."
        )


def _find_story(stories: List[Story], story_id: str) -> Story:
    for index, story in enumerate(stories):
        if _story_id(index) == story_id:
            return story

    valid_ids = ", ".join(_story_id(index) for index in range(len(stories)))
    raise OpenAIChiefEditorError(
        "OpenAI Chief Editor ranked an unknown story id "
        f"'{story_id}'. Expected one of: {valid_ids}."
    )


def _story_id(index: int) -> str:
    return f"story_{index + 1}"
