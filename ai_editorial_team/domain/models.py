from typing import List

from typing_extensions import TypedDict


class Story(TypedDict):
    domain: str
    headline: str
    summary: str
    reason: str


class EditorialDecision(TypedDict):
    selected_story: Story
    editorial_reason: str


class InstagramContent(TypedDict):
    caption: str


class EditorialPackage(EditorialDecision):
    instagram_content: InstagramContent


class EditorialState(TypedDict, total=False):
    stories: List[Story]
    selected_story: Story
    editorial_reason: str
    instagram_content: InstagramContent
