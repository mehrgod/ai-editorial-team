from typing import List, Protocol, runtime_checkable

from ai_editorial_team.domain.models import (
    GeneratedImage,
    ImagePrompt,
    InstagramStoryContent,
    InstagramContent,
    PublicationRequest,
    PublicationResult,
    RankedStory,
    StoredImage,
    XContent,
    Story,
)


class ResearchAgent(Protocol):
    """Interface for agents that provide one candidate story."""

    def research(self) -> Story:
        ...


class ChiefEditor(Protocol):
    """Interface for the agent that ranks candidate stories."""

    def rank_stories(self, stories: List[Story]) -> List[RankedStory]:
        ...


class InstagramContentAgent(Protocol):
    """Interface for agents that generate Instagram content."""

    def generate_caption(self, story: Story) -> InstagramContent:
        ...


class XContentAgent(Protocol):
    """Interface for agents that generate X content."""

    def generate_post(self, ranked_stories: List[RankedStory]) -> XContent:
        ...


class ImagePromptAgent(Protocol):
    """Interface for agents that generate image prompts."""

    def generate_image_prompt(self, story: Story) -> ImagePrompt:
        ...


class ImageGenerator(Protocol):
    """Interface for services that generate and store final images."""

    def generate(self, image_prompt: str) -> GeneratedImage:
        ...


class TemplateImageRenderer(Protocol):
    """Interface for rendering local template images for ranked stories."""

    def render(self, story_content: InstagramStoryContent) -> GeneratedImage:
        ...


class ImageStorage(Protocol):
    """Interface for storing a generated local image externally."""

    def store(self, local_file_path: str) -> StoredImage:
        ...


@runtime_checkable
class SocialPublisher(Protocol):
    """Interface for publishing prepared social content."""

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        ...
