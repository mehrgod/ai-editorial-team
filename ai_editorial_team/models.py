from operator import add
from typing import Annotated, NotRequired, TypedDict


class Story(TypedDict):
    domain: str
    headline: str
    summary: str
    reason: str


class ResearchResult(TypedDict):
    stories: list[Story]


class EditorialDecision(TypedDict):
    selected_story: Story
    editorial_reason: str


class EditorialState(TypedDict):
    # Multiple research nodes write stories in parallel; the reducer appends
    # their lists into one candidate set for the Chief Editor Agent.
    stories: Annotated[list[Story], add]
    selected_story: NotRequired[Story]
    editorial_reason: NotRequired[str]
