from typing import List

from ai_editorial_team.domain.models import EditorialDecision, Story


class DeterministicChiefEditor:
    """Milestone 1 Chief Editor with a fixed selection rule."""

    def select_story(self, stories: List[Story]) -> EditorialDecision:
        if not stories:
            raise ValueError(
                "Chief Editor Agent requires at least one candidate story."
            )

        selected_story = next(
            (
                story
                for story in stories
                if story["domain"] == "Artificial Intelligence"
            ),
            stories[0],
        )

        return {
            "selected_story": selected_story,
            "editorial_reason": (
                "Selected because the AI story has the broadest strategic "
                "impact for a technology-focused audience."
            ),
        }
