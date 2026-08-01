from typing import List

from typing_extensions import NotRequired, TypedDict


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


class XContent(TypedDict):
    post: str


class ImagePrompt(TypedDict):
    image_prompt: str


class GeneratedImage(TypedDict):
    file_path: str


class PublicImageUrl(TypedDict):
    url: str


class PublicationRequest(TypedDict):
    caption: str
    image_url: str


class PublicationResult(TypedDict):
    platform: str
    publication_id: str
    publication_url: NotRequired[str]


class EditorialPackage(EditorialDecision):
    instagram_content: InstagramContent
    x_content: XContent
    image_prompt: ImagePrompt
    generated_image: GeneratedImage
    public_image_url: PublicImageUrl
    publication_result: PublicationResult


class EditorialState(TypedDict, total=False):
    stories: List[Story]
    selected_story: Story
    editorial_reason: str
    instagram_content: InstagramContent
    x_content: XContent
    image_prompt: ImagePrompt
    generated_image: GeneratedImage
    public_image_url: PublicImageUrl
    publication_result: PublicationResult
