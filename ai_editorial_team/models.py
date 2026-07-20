from operator import add
from typing import List

from typing_extensions import Annotated, TypedDict


class Story(TypedDict):
    domain: str
    headline: str
    summary: str
    reason: str


class ResearchResult(TypedDict):
    stories: List[Story]


class EditorialDecision(TypedDict):
    selected_story: Story
    editorial_reason: str


class EditorialStateRequired(TypedDict):
    # Multiple research nodes write stories in parallel; the reducer appends
    # their lists into one candidate set for the Chief Editor Agent.
    stories: Annotated[List[Story], add]


class EditorialState(EditorialStateRequired, total=False):
    selected_story: Story
    editorial_reason: str
