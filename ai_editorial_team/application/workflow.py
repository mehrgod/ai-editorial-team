from dataclasses import dataclass
import logging
from operator import add
from typing import Callable, List

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from ai_editorial_team.domain.models import (
    EditorialPackage,
    InstagramStoryContent,
    MISSING_RSS_SUMMARY,
    PublicationRequest,
    PublicationResult,
    RankedStory,
    Story,
    XContent,
)
from ai_editorial_team.domain.ports import (
    ChiefEditor,
    ImageGenerator,
    ImagePromptAgent,
    ImageStorage,
    InstagramContentAgent,
    ResearchAgent,
    SocialPublisher,
    StorySummaryAgent,
    TemplateImageRenderer,
    XContentAgent,
)


FINANCE_NODE = "Finance Research Agent"
AI_NODE = "AI Research Agent"
SPORTS_NODE = "Sports Research Agent"
EDITOR_NODE = "Chief Editor Agent"
X_CONTENT_NODE = "X Content Agent"
INSTAGRAM_NODE = "Instagram Content Agent"
IMAGE_PROMPT_NODE = "Image Prompt Agent"
IMAGE_GENERATOR_NODE = "Image Generator"
S3_IMAGE_STORAGE_NODE = "S3 Image Storage"
INSTAGRAM_PUBLISHER_NODE = "Instagram Carousel Publisher"
X_PUBLISHER_NODE = "X Publisher"

AI_IMAGE_GENERATION_ENABLED = False

logger = logging.getLogger(__name__)


class ResearchNodeResult(TypedDict):
    stories: List[Story]


class EditorialGraphState(TypedDict, total=False):
    # LangGraph-specific reducer: research nodes each return one story, and the
    # application layer combines them before the Chief Editor runs.
    stories: Annotated[List[Story], add]
    ranked_stories: List[RankedStory]
    instagram_story_contents: List[InstagramStoryContent]
    instagram_publication: PublicationResult
    x_content: XContent
    x_publication: PublicationResult


@dataclass(frozen=True)
class UnavailablePublisher(SocialPublisher):
    """Publisher replacement used when a platform cannot be configured."""

    platform: str
    error: str

    def publish(self, publication: PublicationRequest) -> PublicationResult:
        return _failed_publication(self.platform, RuntimeError(self.error))


@dataclass(frozen=True)
class EditorialWorkflow:
    """Application use case that orchestrates the editorial agents."""

    finance_research_agent: ResearchAgent
    ai_research_agent: ResearchAgent
    sports_research_agent: ResearchAgent
    story_summary_agent: StorySummaryAgent
    chief_editor: ChiefEditor
    x_content_agent: XContentAgent
    instagram_content_agent: InstagramContentAgent
    image_prompt_agent: ImagePromptAgent
    image_generator: ImageGenerator
    template_image_renderer: TemplateImageRenderer
    image_storage: ImageStorage
    instagram_publisher: SocialPublisher
    x_publisher: SocialPublisher

    def run(self) -> EditorialPackage:
        app = self._build_graph()
        result = app.invoke({"stories": []})
        return {
            "instagram_story_contents": result["instagram_story_contents"],
            "instagram_publication": result["instagram_publication"],
            "x_content": result["x_content"],
            "x_publication": result["x_publication"],
        }

    def _build_graph(self):
        graph = StateGraph(EditorialGraphState)

        graph.add_node(FINANCE_NODE, self._research_node(self.finance_research_agent))
        graph.add_node(AI_NODE, self._research_node(self.ai_research_agent))
        graph.add_node(SPORTS_NODE, self._research_node(self.sports_research_agent))
        graph.add_node(EDITOR_NODE, self._chief_editor_node)
        graph.add_node(X_CONTENT_NODE, self._x_content_node)
        graph.add_node(INSTAGRAM_NODE, self._instagram_content_node)
        graph.add_node(IMAGE_PROMPT_NODE, self._image_prompt_node)
        graph.add_node(IMAGE_GENERATOR_NODE, self._image_generator_node)
        graph.add_node(S3_IMAGE_STORAGE_NODE, self._s3_image_storage_node)
        graph.add_node(INSTAGRAM_PUBLISHER_NODE, self._instagram_publisher_node)
        graph.add_node(X_PUBLISHER_NODE, self._x_publisher_node)

        graph.add_edge(START, FINANCE_NODE)
        graph.add_edge(START, AI_NODE)
        graph.add_edge(START, SPORTS_NODE)

        graph.add_edge(FINANCE_NODE, EDITOR_NODE)
        graph.add_edge(AI_NODE, EDITOR_NODE)
        graph.add_edge(SPORTS_NODE, EDITOR_NODE)
        graph.add_edge(EDITOR_NODE, X_CONTENT_NODE)
        graph.add_edge(X_CONTENT_NODE, INSTAGRAM_NODE)
        graph.add_edge(INSTAGRAM_NODE, IMAGE_PROMPT_NODE)
        graph.add_edge(IMAGE_PROMPT_NODE, IMAGE_GENERATOR_NODE)
        graph.add_edge(IMAGE_GENERATOR_NODE, S3_IMAGE_STORAGE_NODE)
        graph.add_edge(S3_IMAGE_STORAGE_NODE, INSTAGRAM_PUBLISHER_NODE)
        graph.add_edge(INSTAGRAM_PUBLISHER_NODE, X_PUBLISHER_NODE)
        graph.add_edge(X_PUBLISHER_NODE, END)

        return graph.compile()

    def _research_node(
        self,
        research_agent: ResearchAgent,
    ) -> Callable[[EditorialGraphState], ResearchNodeResult]:
        def node(_: EditorialGraphState) -> ResearchNodeResult:
            return {"stories": [self._summarize_if_needed(research_agent.research())]}

        return node

    def _summarize_if_needed(self, story: Story) -> Story:
        if _has_real_summary(story["summary"]):
            return story

        return {
            "domain": story["domain"],
            "headline": story["headline"],
            "summary": self.story_summary_agent.summarize_story(story),
            "reason": story["reason"],
        }

    def _chief_editor_node(self, state: EditorialGraphState) -> dict:
        return {"ranked_stories": self.chief_editor.rank_stories(state["stories"])}

    def _x_content_node(self, state: EditorialGraphState) -> dict:
        ranked_stories = state["ranked_stories"]
        _validate_ranked_stories(ranked_stories)
        return {"x_content": self.x_content_agent.generate_post(ranked_stories)}

    def _instagram_content_node(self, state: EditorialGraphState) -> dict:
        return {
            "instagram_story_contents": [
                {
                    "rank": ranked_story["rank"],
                    "story": ranked_story["story"],
                    "editorial_reason": ranked_story["editorial_reason"],
                    "instagram_content": (
                        self.instagram_content_agent.generate_caption(
                            ranked_story["story"]
                        )
                    ),
                }
                for ranked_story in state["ranked_stories"]
            ]
        }

    def _image_prompt_node(self, state: EditorialGraphState) -> dict:
        return {
            "instagram_story_contents": [
                {
                    "rank": story_content["rank"],
                    "story": story_content["story"],
                    "editorial_reason": story_content["editorial_reason"],
                    "instagram_content": story_content["instagram_content"],
                    "image_prompt": self._generate_image_prompt_if_needed(
                        story_content
                    ),
                }
                for story_content in state["instagram_story_contents"]
            ]
        }

    def _generate_image_prompt_if_needed(
        self, story_content: InstagramStoryContent
    ) -> dict:
        if AI_IMAGE_GENERATION_ENABLED and story_content["rank"] == 1:
            return self.image_prompt_agent.generate_image_prompt(story_content["story"])

        return {"image_prompt": ""}

    def _image_generator_node(self, state: EditorialGraphState) -> dict:
        return {
            "instagram_story_contents": [
                {
                    "rank": story_content["rank"],
                    "story": story_content["story"],
                    "editorial_reason": story_content["editorial_reason"],
                    "instagram_content": story_content["instagram_content"],
                    "image_prompt": story_content["image_prompt"],
                    "generated_image": self._generate_story_image(story_content),
                }
                for story_content in state["instagram_story_contents"]
            ]
        }

    def _generate_story_image(self, story_content: InstagramStoryContent) -> dict:
        if AI_IMAGE_GENERATION_ENABLED and story_content["rank"] == 1:
            return self.image_generator.generate(
                story_content["image_prompt"]["image_prompt"]
            )

        return self.template_image_renderer.render(story_content)

    def _s3_image_storage_node(self, state: EditorialGraphState) -> dict:
        return {
            "instagram_story_contents": [
                {
                    "rank": story_content["rank"],
                    "story": story_content["story"],
                    "editorial_reason": story_content["editorial_reason"],
                    "instagram_content": story_content["instagram_content"],
                    "image_prompt": story_content["image_prompt"],
                    "generated_image": story_content["generated_image"],
                    "stored_image": self.image_storage.store(
                        story_content["generated_image"]["file_path"]
                    ),
                }
                for story_content in state["instagram_story_contents"]
            ]
        }

    def _instagram_publisher_node(self, state: EditorialGraphState) -> dict:
        story_contents = state["instagram_story_contents"]

        try:
            _validate_carousel_story_contents(story_contents)
            publication = self.instagram_publisher.publish(
                {
                    "caption": _build_carousel_caption(story_contents),
                    "image_urls": [
                        story_content["stored_image"]["public_url"]
                        for story_content in story_contents
                    ],
                }
            )
        except Exception as exc:
            publication = _failed_publication("Instagram", exc)

        return {"instagram_publication": publication}

    def _x_publisher_node(self, state: EditorialGraphState) -> dict:
        story_contents = state["instagram_story_contents"]
        x_content = state["x_content"]

        try:
            _validate_x_publication_inputs(story_contents, x_content)
            publication = self.x_publisher.publish(
                {
                    "text": x_content["post"],
                    "image_paths": [
                        story_content["generated_image"]["file_path"]
                        for story_content in story_contents
                    ],
                }
            )
        except Exception as exc:
            publication = _failed_publication("X", exc)

        return {"x_publication": publication}


def _has_real_summary(summary: str) -> bool:
    normalized = summary.strip().lower()
    return bool(normalized) and normalized not in {
        MISSING_RSS_SUMMARY.lower(),
        "null",
        "none",
        "n/a",
    }


def _build_carousel_caption(
    story_contents: List[InstagramStoryContent],
) -> str:
    return "\n\n".join(
        f"{story_content['rank']}. " f"{story_content['instagram_content']['caption']}"
        for story_content in story_contents
    )


def _failed_publication(platform: str, exc: Exception) -> PublicationResult:
    logger.warning("%s publishing failed; continuing workflow: %s", platform, exc)
    return {
        "platform": platform,
        "publication_id": "",
        "publication_url": "",
        "status": "failed",
        "error": str(exc),
    }


def _validate_ranked_stories(ranked_stories: List[RankedStory]) -> None:
    if len(ranked_stories) != 3:
        raise ValueError("X content generation requires exactly 3 ranked stories.")

    ranks = [ranked_story["rank"] for ranked_story in ranked_stories]
    if ranks != [1, 2, 3]:
        raise ValueError(
            "X content generation requires ranked stories ordered by rank 1, 2, 3."
        )


def _validate_carousel_story_contents(
    story_contents: List[InstagramStoryContent],
) -> None:
    if len(story_contents) != 3:
        raise ValueError(
            "Instagram carousel publishing requires exactly 3 ranked story items."
        )

    ranks = [story_content["rank"] for story_content in story_contents]
    if ranks != [1, 2, 3]:
        raise ValueError(
            "Instagram carousel publishing requires story items ordered by "
            "rank 1, 2, 3."
        )

    for story_content in story_contents:
        if not story_content["stored_image"]["public_url"]:
            raise ValueError(
                "Instagram carousel publishing requires every story item to "
                "have a stored image URL."
            )


def _validate_x_publication_inputs(
    story_contents: List[InstagramStoryContent],
    x_content: XContent,
) -> None:
    if len(story_contents) != 3:
        raise ValueError("X publishing requires exactly 3 ranked story items.")

    ranks = [story_content["rank"] for story_content in story_contents]
    if ranks != [1, 2, 3]:
        raise ValueError("X publishing requires story items ordered by rank 1, 2, 3.")

    for story_content in story_contents:
        if not story_content["generated_image"]["file_path"]:
            raise ValueError(
                "X publishing requires every story item to have a generated image path."
            )

    post = x_content["post"]
    if not post:
        raise ValueError("X publishing requires generated post text.")
    if len(post) > 250:
        raise ValueError("X publishing requires generated post text <= 250 characters.")
