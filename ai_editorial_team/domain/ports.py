from typing import List, Protocol

from ai_editorial_team.domain.models import (
    EditorialDecision,
    InstagramContent,
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
