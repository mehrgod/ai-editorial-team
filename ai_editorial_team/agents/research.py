from ai_editorial_team.models import ResearchResult


def finance_research_agent(_: dict) -> ResearchResult:
    """Return the Finance candidate story."""
    return {
        "stories": [
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
        ]
    }


def ai_research_agent(_: dict) -> ResearchResult:
    """Return the Artificial Intelligence candidate story."""
    return {
        "stories": [
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
        ]
    }


def sports_research_agent(_: dict) -> ResearchResult:
    """Return the Sports candidate story."""
    return {
        "stories": [
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
        ]
    }
