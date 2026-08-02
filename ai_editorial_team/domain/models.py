from typing import List

from typing_extensions import NotRequired, TypedDict


class Story(TypedDict):
    domain: str
    headline: str
    summary: str
    reason: str


class RankedStory(TypedDict):
    rank: int
    story: Story
    editorial_reason: str


class EditorialPackage(TypedDict):
    instagram_story_contents: List["InstagramStoryContent"]


class InstagramContent(TypedDict):
    caption: str


class InstagramStoryContent(RankedStory):
    instagram_content: InstagramContent
    image_prompt: "ImagePrompt"
    generated_image: "GeneratedImage"


class XContent(TypedDict):
    post: str


class ImagePrompt(TypedDict):
    image_prompt: str


class GeneratedImage(TypedDict):
    file_path: str


class StoredImage(TypedDict):
    object_key: str
    public_url: str


class PublicationRequest(TypedDict):
    caption: NotRequired[str]
    image_url: NotRequired[str]
    text: NotRequired[str]


class PublicationResult(TypedDict):
    platform: str
    publication_id: str
    publication_url: str


class EditorialState(TypedDict, total=False):
    stories: List[Story]
    ranked_stories: List[RankedStory]
    instagram_story_contents: List[InstagramStoryContent]
