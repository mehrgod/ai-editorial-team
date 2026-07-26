from dataclasses import dataclass
from datetime import date
import json
import os
from typing import List, Optional

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from ai_editorial_team.domain.models import EditorialDecision, Story


DEFAULT_OPENAI_MODEL = "gpt-5.5"


class OpenAIChiefEditorError(RuntimeError):
    """Raised when the LLM Chief Editor cannot produce a decision."""


class OpenAIConfigurationError(OpenAIChiefEditorError):
    """Raised when required OpenAI configuration is missing."""


@dataclass(frozen=True)
class OpenAIChiefEditorConfig:
    api_key: str
    model: str = DEFAULT_OPENAI_MODEL

    @classmethod
    def from_env(cls) -> "OpenAIChiefEditorConfig":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is not set. Set it in your environment before "
                "running the application."
            )

        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
        )


class EditorialSelectionResponse(BaseModel):
    selected_story_id: str = Field(
        description="The id of exactly one selected candidate story."
    )
    editorial_reason: str = Field(
        description="A concise explanation of why this story was selected."
    )


class LLMChiefEditor:
    """OpenAI-powered Chief Editor that implements the domain ChiefEditor port."""

    def __init__(
        self,
        config: OpenAIChiefEditorConfig,
        client: Optional[OpenAI] = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAI(api_key=config.api_key)

    def select_story(self, stories: List[Story]) -> EditorialDecision:
        if not stories:
            raise OpenAIChiefEditorError(
                "LLM Chief Editor requires at least one candidate story."
            )

        story_options = _build_story_options(stories)

        try:
            response = self._client.responses.parse(
                model=self._config.model,
                instructions=_editor_instructions(),
                input=_editor_prompt(story_options),
                text_format=EditorialSelectionResponse,
                store=False,
            )
        except OpenAIError as exc:
            raise OpenAIChiefEditorError(
                f"OpenAI Chief Editor request failed: {exc}"
            ) from exc
        except ValidationError as exc:
            raise OpenAIChiefEditorError(
                f"OpenAI Chief Editor returned invalid structured output: {exc}"
            ) from exc

        selection = response.output_parsed
        if selection is None:
            raise OpenAIChiefEditorError(
                "OpenAI Chief Editor did not return structured output."
            )

        selected_story = _find_selected_story(
            stories, story_options, selection.selected_story_id
        )

        return {
            "selected_story": selected_story,
            "editorial_reason": selection.editorial_reason,
        }


def _editor_instructions() -> str:
    return (
        "You are the Chief Editor for an AI-powered editorial team. "
        "Evaluate the candidate stories and select the single best story for "
        "today's audience. Consider newsworthiness, broad audience appeal, "
        "timeliness, potential engagement, and clarity. Return only structured "
        "JSON matching the provided schema. Do not include free-form text."
    )


def _editor_prompt(story_options: List[dict]) -> str:
    return (
        f"Today is {date.today().isoformat()}.\n"
        "Select exactly one candidate story from this JSON array:\n"
        f"{json.dumps(story_options, indent=2)}\n"
        "The selected_story_id must match exactly one provided id."
    )


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


def _find_selected_story(
    stories: List[Story], story_options: List[dict], selected_story_id: str
) -> Story:
    for story, option in zip(stories, story_options):
        if option["id"] == selected_story_id:
            return story

    valid_ids = ", ".join(option["id"] for option in story_options)
    raise OpenAIChiefEditorError(
        "OpenAI Chief Editor selected an unknown story id "
        f"'{selected_story_id}'. Expected one of: {valid_ids}."
    )


def _story_id(index: int) -> str:
    return f"story_{index + 1}"
