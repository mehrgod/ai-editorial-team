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


class RecordingXContentAgent:
    def __init__(self) -> None:
        self.received_ranked_stories = []

    def generate_post(self, ranked_stories):
        self.received_ranked_stories.append(list(ranked_stories))
        return {
            "post": (
                "1/ Sports headline 2/ AI headline "
                "3/ Finance headline"
            )
        }


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


class RecordingInstagramPublisher:
    def __init__(self) -> None:
        self.received_publications = []

    def publish(self, publication):
        self.received_publications.append(publication)
        return {
            "platform": "Instagram",
            "publication_id": "carousel-123",
            "publication_url": "https://instagram.com/p/carousel-123",
        }


class RecordingXPublisher:
    def __init__(self) -> None:
        self.received_publications = []

    def publish(self, publication):
        self.received_publications.append(publication)
        return {
            "platform": "X",
            "publication_id": "x-post-123",
            "publication_url": "https://x.com/i/web/status/x-post-123",
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
        self.x_content_agent = RecordingXContentAgent()
        self.image_prompt_agent = RecordingImagePromptAgent()
        self.image_generator = RecordingImageGenerator()
        self.image_storage = RecordingImageStorage()
        self.instagram_publisher = RecordingInstagramPublisher()
        self.x_publisher = RecordingXPublisher()
        self.workflow = EditorialWorkflow(
            finance_research_agent=FakeResearchAgent(self.finance_story),
            ai_research_agent=FakeResearchAgent(self.ai_story),
            sports_research_agent=FakeResearchAgent(self.sports_story),
            chief_editor=self.chief_editor,
            x_content_agent=self.x_content_agent,
            instagram_content_agent=self.instagram_content_agent,
            image_prompt_agent=self.image_prompt_agent,
            image_generator=self.image_generator,
            image_storage=self.image_storage,
            instagram_publisher=self.instagram_publisher,
            x_publisher=self.x_publisher,
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

    def test_x_content_agent_receives_all_ranked_stories_in_order(self):
        self.workflow.run()

        self.assertEqual(len(self.x_content_agent.received_ranked_stories), 1)
        ranked_stories = self.x_content_agent.received_ranked_stories[0]
        self.assertEqual(
            [ranked_story["rank"] for ranked_story in ranked_stories],
            [1, 2, 3],
        )
        self.assertEqual(
            [
                ranked_story["story"]["headline"]
                for ranked_story in ranked_stories
            ],
            ["Sports headline", "AI headline", "Finance headline"],
        )

    def test_combined_x_post_contains_all_stories_in_rank_order(self):
        result = self.workflow.run()
        post = result["x_content"]["post"]

        self.assertLessEqual(len(post), 250)
        self.assertIn("Sports headline", post)
        self.assertIn("AI headline", post)
        self.assertIn("Finance headline", post)
        self.assertLess(post.index("Sports headline"), post.index("AI headline"))
        self.assertLess(post.index("AI headline"), post.index("Finance headline"))

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

    def test_instagram_publisher_receives_rank_ordered_carousel_once(self):
        self.workflow.run()

        self.assertEqual(len(self.instagram_publisher.received_publications), 1)
        self.assertEqual(
            self.instagram_publisher.received_publications[0],
            {
                "caption": (
                    "1. Caption for Sports headline\n\n"
                    "2. Caption for AI headline\n\n"
                    "3. Caption for Finance headline"
                ),
                "image_urls": [
                    "https://example.com/generated_1.png",
                    "https://example.com/generated_2.png",
                    "https://example.com/generated_3.png",
                ],
            },
        )

    def test_instagram_carousel_caption_combines_all_captions_in_rank_order(self):
        self.workflow.run()

        self.assertEqual(len(self.instagram_publisher.received_publications), 1)
        caption = self.instagram_publisher.received_publications[0]["caption"]

        self.assertIn("1. Caption for Sports headline", caption)
        self.assertIn("2. Caption for AI headline", caption)
        self.assertIn("3. Caption for Finance headline", caption)
        self.assertLess(
            caption.index("1. Caption for Sports headline"),
            caption.index("2. Caption for AI headline"),
        )
        self.assertLess(
            caption.index("2. Caption for AI headline"),
            caption.index("3. Caption for Finance headline"),
        )

    def test_final_publication_result_is_returned(self):
        result = self.workflow.run()

        self.assertEqual(
            result["instagram_publication"],
            {
                "platform": "Instagram",
                "publication_id": "carousel-123",
                "publication_url": "https://instagram.com/p/carousel-123",
            },
        )

    def test_x_publisher_receives_combined_post_and_ranked_image_paths_once(self):
        self.workflow.run()

        self.assertEqual(len(self.x_publisher.received_publications), 1)
        self.assertEqual(
            self.x_publisher.received_publications[0],
            {
                "text": (
                    "1/ Sports headline 2/ AI headline "
                    "3/ Finance headline"
                ),
                "image_paths": [
                    "output/images/generated_1.png",
                    "output/images/generated_2.png",
                    "output/images/generated_3.png",
                ],
            },
        )

    def test_final_x_publication_result_is_returned(self):
        result = self.workflow.run()

        self.assertEqual(
            result["x_publication"],
            {
                "platform": "X",
                "publication_id": "x-post-123",
                "publication_url": "https://x.com/i/web/status/x-post-123",
            },
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
        self.assertIn("Instagram Carousel Published", rendered_output)
        self.assertIn("Platform: Instagram", rendered_output)
        self.assertIn("Publication ID: carousel-123", rendered_output)
        self.assertIn("URL: https://instagram.com/p/carousel-123", rendered_output)
        self.assertIn("X Post", rendered_output)
        self.assertIn(
            "1/ Sports headline 2/ AI headline 3/ Finance headline",
            rendered_output,
        )
        self.assertIn("X Published", rendered_output)
        self.assertIn("Publication ID: x-post-123", rendered_output)
        self.assertIn("URL: https://x.com/i/web/status/x-post-123", rendered_output)
