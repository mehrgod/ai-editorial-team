from dataclasses import dataclass
from operator import add
from typing import Callable, List

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from ai_editorial_team.domain.models import (
    EditorialDecision,
    EditorialPackage,
    GeneratedImage,
    ImagePrompt,
    InstagramContent,
    PublicationResult,
    PublicImageUrl,
    XContent,
    Story,
)
from ai_editorial_team.domain.ports import (
    ChiefEditor,
    ImageGenerator,
    ImagePromptAgent,
    ImageUrlProvider,
    InstagramContentAgent,
    ResearchAgent,
    SocialPublisher,
    XContentAgent,
)


FINANCE_NODE = "Finance Research Agent"
AI_NODE = "AI Research Agent"
SPORTS_NODE = "Sports Research Agent"
EDITOR_NODE = "Chief Editor Agent"
INSTAGRAM_NODE = "Instagram Content Agent"
X_NODE = "X Content Agent"
IMAGE_PROMPT_NODE = "Image Prompt Agent"
IMAGE_GENERATOR_NODE = "Image Generator"
IMAGE_URL_PROVIDER_NODE = "Image URL Provider"
INSTAGRAM_PUBLISHER_NODE = "Instagram Publisher"


class ResearchNodeResult(TypedDict):
    stories: List[Story]


class EditorialGraphState(TypedDict, total=False):
    # LangGraph-specific reducer: research nodes each return one story, and the
    # application layer combines them before the Chief Editor runs.
    stories: Annotated[List[Story], add]
    selected_story: Story
    editorial_reason: str
    instagram_content: InstagramContent
    x_content: XContent
    image_prompt: ImagePrompt
    generated_image: GeneratedImage
    public_image_url: PublicImageUrl
    publication_result: PublicationResult


@dataclass(frozen=True)
class EditorialWorkflow:
    """Application use case that orchestrates the editorial agents."""

    finance_research_agent: ResearchAgent
    ai_research_agent: ResearchAgent
    sports_research_agent: ResearchAgent
    chief_editor: ChiefEditor
    instagram_content_agent: InstagramContentAgent
    x_content_agent: XContentAgent
    image_prompt_agent: ImagePromptAgent
    image_generator: ImageGenerator
    image_url_provider: ImageUrlProvider
    social_publisher: SocialPublisher

    def run(self) -> EditorialPackage:
        app = self._build_graph()
        result = app.invoke({"stories": []})
        return {
            "selected_story": result["selected_story"],
            "editorial_reason": result["editorial_reason"],
            "instagram_content": result["instagram_content"],
            "x_content": result["x_content"],
            "image_prompt": result["image_prompt"],
            "generated_image": result["generated_image"],
            "public_image_url": result["public_image_url"],
            "publication_result": result["publication_result"],
        }

    def _build_graph(self):
        graph = StateGraph(EditorialGraphState)

        graph.add_node(
            FINANCE_NODE, self._research_node(self.finance_research_agent)
        )
        graph.add_node(AI_NODE, self._research_node(self.ai_research_agent))
        graph.add_node(
            SPORTS_NODE, self._research_node(self.sports_research_agent)
        )
        graph.add_node(EDITOR_NODE, self._chief_editor_node)
        graph.add_node(INSTAGRAM_NODE, self._instagram_content_node)
        graph.add_node(X_NODE, self._x_content_node)
        graph.add_node(IMAGE_PROMPT_NODE, self._image_prompt_node)
        graph.add_node(IMAGE_GENERATOR_NODE, self._image_generator_node)
        graph.add_node(IMAGE_URL_PROVIDER_NODE, self._image_url_provider_node)
        graph.add_node(INSTAGRAM_PUBLISHER_NODE, self._instagram_publisher_node)

        graph.add_edge(START, FINANCE_NODE)
        graph.add_edge(START, AI_NODE)
        graph.add_edge(START, SPORTS_NODE)

        graph.add_edge(FINANCE_NODE, EDITOR_NODE)
        graph.add_edge(AI_NODE, EDITOR_NODE)
        graph.add_edge(SPORTS_NODE, EDITOR_NODE)
        graph.add_edge(EDITOR_NODE, INSTAGRAM_NODE)
        graph.add_edge(INSTAGRAM_NODE, X_NODE)
        graph.add_edge(X_NODE, IMAGE_PROMPT_NODE)
        graph.add_edge(IMAGE_PROMPT_NODE, IMAGE_GENERATOR_NODE)
        graph.add_edge(IMAGE_GENERATOR_NODE, IMAGE_URL_PROVIDER_NODE)
        graph.add_edge(IMAGE_URL_PROVIDER_NODE, INSTAGRAM_PUBLISHER_NODE)
        graph.add_edge(INSTAGRAM_PUBLISHER_NODE, END)

        return graph.compile()

    @staticmethod
    def _research_node(
        research_agent: ResearchAgent,
    ) -> Callable[[EditorialGraphState], ResearchNodeResult]:
        def node(_: EditorialGraphState) -> ResearchNodeResult:
            return {"stories": [research_agent.research()]}

        return node

    def _chief_editor_node(
        self, state: EditorialGraphState
    ) -> EditorialDecision:
        return self.chief_editor.select_story(state["stories"])

    def _instagram_content_node(
        self, state: EditorialGraphState
    ) -> dict:
        return {
            "instagram_content": self.instagram_content_agent.generate_caption(
                state["selected_story"]
            )
        }

    def _x_content_node(self, state: EditorialGraphState) -> dict:
        return {
            "x_content": self.x_content_agent.generate_post(
                state["selected_story"]
            )
        }

    def _image_prompt_node(self, state: EditorialGraphState) -> dict:
        return {
            "image_prompt": self.image_prompt_agent.generate_image_prompt(
                state["selected_story"]
            )
        }

    def _image_generator_node(
        self, state: EditorialGraphState
    ) -> dict:
        return {
            "generated_image": self.image_generator.generate(
                state["image_prompt"]["image_prompt"]
            )
        }

    def _image_url_provider_node(
        self, state: EditorialGraphState
    ) -> dict:
        return {
            "public_image_url": self.image_url_provider.provide_url(
                state["generated_image"]
            )
        }

    def _instagram_publisher_node(
        self, state: EditorialGraphState
    ) -> dict:
        return {
            "publication_result": self.social_publisher.publish(
                {
                    "caption": state["instagram_content"]["caption"],
                    "image_url": state["public_image_url"]["url"],
                }
            )
        }
