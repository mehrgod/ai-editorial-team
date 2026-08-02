from typing import List

from ai_editorial_team.domain.models import RankedStory, Story


class DeterministicChiefEditor:
    """Milestone 1 Chief Editor with a fixed selection rule."""

    def rank_stories(self, stories: List[Story]) -> List[RankedStory]:
        if not stories:
            raise ValueError(
                "Chief Editor Agent requires at least one candidate story."
            )

        return [
            {
                "rank": index + 1,
                "story": story,
                "editorial_reason": "Ranked deterministically for local testing.",
            }
            for index, story in enumerate(stories)
        ]
