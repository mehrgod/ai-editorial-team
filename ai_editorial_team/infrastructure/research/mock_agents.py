from dataclasses import dataclass
from typing import cast

from ai_editorial_team.domain.models import Story
from ai_editorial_team.domain.ports import ResearchAgent


@dataclass(frozen=True)
class MockResearchAgent:
    """Infrastructure adapter that returns static Milestone 1 research data."""

    story: Story

    def research(self) -> Story:
        return cast(Story, self.story.copy())


def create_finance_research_agent() -> ResearchAgent:
    return MockResearchAgent(
        {
            "domain": "Finance",
            "headline": "Markets Rally as Investors Price In Softer Inflation",
            "summary": (
                "Major indexes moved higher after new inflation signals "
                "suggested price pressures may be easing."
            ),
            "reason": (
                "Inflation expectations affect interest rates, consumer "
                "spending, and portfolio strategy."
            ),
        }
    )


def create_ai_research_agent() -> ResearchAgent:
    return MockResearchAgent(
        {
            "domain": "Artificial Intelligence",
            "headline": "New Multimodal AI Systems Move From Demos to Daily Workflows",
            "summary": (
                "AI products are increasingly combining text, images, audio, "
                "and tool use inside practical workplace experiences."
            ),
            "reason": (
                "This shift signals AI moving from novelty toward durable "
                "productivity infrastructure."
            ),
        }
    )


def create_sports_research_agent() -> ResearchAgent:
    return MockResearchAgent(
        {
            "domain": "Sports",
            "headline": "Underdog Team Extends Playoff Run With Late Comeback",
            "summary": (
                "A dramatic fourth-quarter surge kept the team's postseason "
                "hopes alive and shifted momentum in the series."
            ),
            "reason": (
                "Comeback stories create strong emotional pull and are easy "
                "for a broad audience to follow."
            ),
        }
    )
