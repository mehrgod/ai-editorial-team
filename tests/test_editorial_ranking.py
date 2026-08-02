import io
import unittest
from contextlib import redirect_stdout

from ai_editorial_team.application.workflow import EditorialWorkflow
from ai_editorial_team.domain.models import Story
from ai_editorial_team.presentation.cli import run_cli


class FakeResearchAgent:
    def __init__(self, story: Story) -> None:
        self._story = story

    def research(self) -> Story:
        return self._story


class RecordingChiefEditor:
    def __init__(self) -> None:
        self.received_stories = []

    def rank_stories(self, stories):
        self.received_stories = list(stories)
        stories_by_domain = {story["domain"]: story for story in stories}
        ranked_order = [
            stories_by_domain["Sports"],
            stories_by_domain["Artificial Intelligence"],
            stories_by_domain["Finance"],
        ]
        return [
            {
                "rank": index + 1,
                "story": story,
                "editorial_reason": f"Reason {index + 1}",
            }
            for index, story in enumerate(ranked_order)
        ]


class EditorialRankingWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.finance_story = {
            "domain": "Finance",
            "headline": "Finance headline",
            "summary": "Finance summary",
            "reason": "Finance reason",
        }
        self.ai_story = {
            "domain": "Artificial Intelligence",
            "headline": "AI headline",
            "summary": "AI summary",
            "reason": "AI reason",
        }
        self.sports_story = {
            "domain": "Sports",
            "headline": "Sports headline",
            "summary": "Sports summary",
            "reason": "Sports reason",
        }
        self.chief_editor = RecordingChiefEditor()
        self.workflow = EditorialWorkflow(
            finance_research_agent=FakeResearchAgent(self.finance_story),
            ai_research_agent=FakeResearchAgent(self.ai_story),
            sports_research_agent=FakeResearchAgent(self.sports_story),
            chief_editor=self.chief_editor,
        )

    def test_all_three_stories_are_passed_to_chief_editor(self):
        self.workflow.run()

        self.assertEqual(len(self.chief_editor.received_stories), 3)
        self.assertEqual(
            {
                story["headline"]
                for story in self.chief_editor.received_stories
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_all_three_stories_are_returned_with_exact_ranks_no_duplicates(self):
        result = self.workflow.run()
        ranked_stories = result["ranked_stories"]

        self.assertEqual(len(ranked_stories), 3)
        self.assertEqual(
            [ranked_story["rank"] for ranked_story in ranked_stories],
            [1, 2, 3],
        )
        self.assertEqual(
            {
                ranked_story["story"]["headline"]
                for ranked_story in ranked_stories
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_cli_shows_ranked_order(self):
        output = io.StringIO()

        with redirect_stdout(output):
            run_cli(self.workflow)

        rendered_output = output.getvalue()
        self.assertIn("Ranked Stories", rendered_output)
        self.assertIn("1. [Sports] Sports headline", rendered_output)
        self.assertIn("   Editorial Reason: Reason 1", rendered_output)
        self.assertIn("2. [Artificial Intelligence] AI headline", rendered_output)
        self.assertIn("   Editorial Reason: Reason 2", rendered_output)
        self.assertIn("3. [Finance] Finance headline", rendered_output)
        self.assertIn("   Editorial Reason: Reason 3", rendered_output)
