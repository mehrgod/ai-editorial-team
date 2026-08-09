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


class RecordingInstagramContentAgent:
    def __init__(self) -> None:
        self.received_stories = []

    def generate_caption(self, story: Story):
        self.received_stories.append(story)
        return {"caption": f"Caption for {story['headline']}"}


class RecordingImagePromptAgent:
    def __init__(self) -> None:
        self.received_stories = []

    def generate_image_prompt(self, story: Story):
        self.received_stories.append(story)
        return {"image_prompt": f"Image prompt for {story['headline']}"}


class RecordingImageGenerator:
    def __init__(self) -> None:
        self.received_prompts = []

    def generate(self, image_prompt: str):
        self.received_prompts.append(image_prompt)
        return {"file_path": f"output/images/generated_{len(self.received_prompts)}.png"}


class RecordingImageStorage:
    def __init__(self) -> None:
        self.received_file_paths = []

    def store(self, local_file_path: str):
        self.received_file_paths.append(local_file_path)
        index = len(self.received_file_paths)
        return {
            "object_key": f"images/generated_{index}.png",
            "public_url": f"https://example.com/generated_{index}.png",
        }


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
        self.instagram_content_agent = RecordingInstagramContentAgent()
        self.image_prompt_agent = RecordingImagePromptAgent()
        self.image_generator = RecordingImageGenerator()
        self.image_storage = RecordingImageStorage()
        self.workflow = EditorialWorkflow(
            finance_research_agent=FakeResearchAgent(self.finance_story),
            ai_research_agent=FakeResearchAgent(self.ai_story),
            sports_research_agent=FakeResearchAgent(self.sports_story),
            chief_editor=self.chief_editor,
            instagram_content_agent=self.instagram_content_agent,
            image_prompt_agent=self.image_prompt_agent,
            image_generator=self.image_generator,
            image_storage=self.image_storage,
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
        ranked_stories = result["instagram_story_contents"]

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

    def test_instagram_agent_is_called_once_for_each_ranked_story_in_order(self):
        self.workflow.run()

        self.assertEqual(len(self.instagram_content_agent.received_stories), 3)
        self.assertEqual(
            [
                story["headline"]
                for story in self.instagram_content_agent.received_stories
            ],
            ["Sports headline", "AI headline", "Finance headline"],
        )

    def test_every_ranked_story_has_caption_with_no_duplicates_or_drops(self):
        result = self.workflow.run()
        story_contents = result["instagram_story_contents"]

        self.assertEqual(
            [story_content["rank"] for story_content in story_contents],
            [1, 2, 3],
        )
        self.assertEqual(
            [
                story_content["instagram_content"]["caption"]
                for story_content in story_contents
            ],
            [
                "Caption for Sports headline",
                "Caption for AI headline",
                "Caption for Finance headline",
            ],
        )
        self.assertEqual(
            {
                story_content["story"]["headline"]
                for story_content in story_contents
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_image_prompt_agent_is_called_once_for_each_ranked_story_in_order(self):
        self.workflow.run()

        self.assertEqual(len(self.image_prompt_agent.received_stories), 3)
        self.assertEqual(
            [
                story["headline"]
                for story in self.image_prompt_agent.received_stories
            ],
            ["Sports headline", "AI headline", "Finance headline"],
        )

    def test_every_ranked_story_has_image_prompt_with_no_duplicates_or_drops(self):
        result = self.workflow.run()
        story_contents = result["instagram_story_contents"]

        self.assertEqual(
            [story_content["rank"] for story_content in story_contents],
            [1, 2, 3],
        )
        self.assertEqual(
            [
                story_content["image_prompt"]["image_prompt"]
                for story_content in story_contents
            ],
            [
                "Image prompt for Sports headline",
                "Image prompt for AI headline",
                "Image prompt for Finance headline",
            ],
        )
        self.assertEqual(
            {
                story_content["story"]["headline"]
                for story_content in story_contents
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_image_generator_is_called_once_for_each_image_prompt_in_order(self):
        self.workflow.run()

        self.assertEqual(len(self.image_generator.received_prompts), 3)
        self.assertEqual(
            self.image_generator.received_prompts,
            [
                "Image prompt for Sports headline",
                "Image prompt for AI headline",
                "Image prompt for Finance headline",
            ],
        )

    def test_every_ranked_story_has_generated_image_with_no_duplicates_or_drops(self):
        result = self.workflow.run()
        story_contents = result["instagram_story_contents"]

        self.assertEqual(
            [story_content["rank"] for story_content in story_contents],
            [1, 2, 3],
        )
        self.assertEqual(
            [
                story_content["generated_image"]["file_path"]
                for story_content in story_contents
            ],
            [
                "output/images/generated_1.png",
                "output/images/generated_2.png",
                "output/images/generated_3.png",
            ],
        )
        self.assertEqual(
            {
                story_content["story"]["headline"]
                for story_content in story_contents
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_image_storage_is_called_once_for_each_generated_image_in_order(self):
        self.workflow.run()

        self.assertEqual(len(self.image_storage.received_file_paths), 3)
        self.assertEqual(
            self.image_storage.received_file_paths,
            [
                "output/images/generated_1.png",
                "output/images/generated_2.png",
                "output/images/generated_3.png",
            ],
        )

    def test_every_ranked_story_has_stored_image_with_no_duplicates_or_drops(self):
        result = self.workflow.run()
        story_contents = result["instagram_story_contents"]

        self.assertEqual(
            [story_content["rank"] for story_content in story_contents],
            [1, 2, 3],
        )
        self.assertEqual(
            [
                story_content["stored_image"]["object_key"]
                for story_content in story_contents
            ],
            [
                "images/generated_1.png",
                "images/generated_2.png",
                "images/generated_3.png",
            ],
        )
        self.assertEqual(
            [
                story_content["stored_image"]["public_url"]
                for story_content in story_contents
            ],
            [
                "https://example.com/generated_1.png",
                "https://example.com/generated_2.png",
                "https://example.com/generated_3.png",
            ],
        )
        self.assertEqual(
            {
                story_content["story"]["headline"]
                for story_content in story_contents
            },
            {"Finance headline", "AI headline", "Sports headline"},
        )

    def test_cli_shows_ranked_order(self):
        output = io.StringIO()

        with redirect_stdout(output):
            run_cli(self.workflow)

        rendered_output = output.getvalue()
        self.assertIn("Rank 1", rendered_output)
        self.assertIn("Domain: Sports", rendered_output)
        self.assertIn("Headline: Sports headline", rendered_output)
        self.assertIn("Editorial Reason: Reason 1", rendered_output)
        self.assertIn("Instagram Caption: Caption for Sports headline", rendered_output)
        self.assertIn("Image Prompt: Image prompt for Sports headline", rendered_output)
        self.assertIn("Generated Image: output/images/generated_1.png", rendered_output)
        self.assertIn("S3 Object Key: images/generated_1.png", rendered_output)
        self.assertIn(
            "Presigned Image URL: https://example.com/generated_1.png",
            rendered_output,
        )
        self.assertIn("Rank 2", rendered_output)
        self.assertIn("Domain: Artificial Intelligence", rendered_output)
        self.assertIn("Instagram Caption: Caption for AI headline", rendered_output)
        self.assertIn("Image Prompt: Image prompt for AI headline", rendered_output)
        self.assertIn("Generated Image: output/images/generated_2.png", rendered_output)
        self.assertIn("S3 Object Key: images/generated_2.png", rendered_output)
        self.assertIn(
            "Presigned Image URL: https://example.com/generated_2.png",
            rendered_output,
        )
        self.assertIn("Rank 3", rendered_output)
        self.assertIn("Domain: Finance", rendered_output)
        self.assertIn("Instagram Caption: Caption for Finance headline", rendered_output)
        self.assertIn("Image Prompt: Image prompt for Finance headline", rendered_output)
        self.assertIn("Generated Image: output/images/generated_3.png", rendered_output)
        self.assertIn("S3 Object Key: images/generated_3.png", rendered_output)
        self.assertIn(
            "Presigned Image URL: https://example.com/generated_3.png",
            rendered_output,
        )
