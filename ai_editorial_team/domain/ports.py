from typing import List, Protocol, runtime_checkable

from ai_editorial_team.domain.models import (
    EditorialDecision,
    GeneratedImage,
    ImagePrompt,
    InstagramContent,
    PublicationRequest,
    PublicationResult,
    StoredImage,
    XContent,
    Story,
)


class ResearchAgent(Protocol):
    """Interface for agents that provide one candidate story."""

    def research(self) -> Story:
        ...


class ChiefEditor(Protocol):
    """Interface for the agent that selects the final story."""

    def select_story(self, stories: List[Story]) -> EditorialDecision:
        ...


class InstagramContentAgent(Protocol):
    """Interface for agents that generate Instagram content."""

    def generate_caption(self, story: Story) -> InstagramContent:
        ...


class XContentAgent(Protocol):
    """Interface for agents that generate X content."""

    def generate_post(self, story: Story) -> XContent:
        ...


class ImagePromptAgent(Protocol):
    """Interface for agents that generate image prompts."""

    def generate_image_prompt(self, story: Story) -> ImagePrompt:
        ...


class ImageGenerator(Protocol):
    """Interface for services that generate and store final images."""

    def generate(self, image_prompt: str) -> GeneratedImage:
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
