from dataclasses import dataclass
from operator import add
from typing import Callable, List

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from ai_editorial_team.domain.models import (
    EditorialDecision,
    EditorialPackage,
    InstagramContent,
    Story,
)
from ai_editorial_team.domain.ports import (
    ChiefEditor,
    InstagramContentAgent,
    ResearchAgent,
)


FINANCE_NODE = "Finance Research Agent"
AI_NODE = "AI Research Agent"
SPORTS_NODE = "Sports Research Agent"
EDITOR_NODE = "Chief Editor Agent"
INSTAGRAM_NODE = "Instagram Content Agent"


class ResearchNodeResult(TypedDict):
    stories: List[Story]


class EditorialGraphState(TypedDict, total=False):
    # LangGraph-specific reducer: research nodes each return one story, and the
    # application layer combines them before the Chief Editor runs.
    stories: Annotated[List[Story], add]
    selected_story: Story
    editorial_reason: str
    instagram_content: InstagramContent


@dataclass(frozen=True)
class EditorialWorkflow:
    """Application use case that orchestrates the editorial agents."""

    finance_research_agent: ResearchAgent
    ai_research_agent: ResearchAgent
    sports_research_agent: ResearchAgent
    chief_editor: ChiefEditor
    instagram_content_agent: InstagramContentAgent

    def run(self) -> EditorialPackage:
        app = self._build_graph()
        result = app.invoke({"stories": []})
        return {
            "selected_story": result["selected_story"],
            "editorial_reason": result["editorial_reason"],
            "instagram_content": result["instagram_content"],
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

        graph.add_edge(START, FINANCE_NODE)
        graph.add_edge(START, AI_NODE)
        graph.add_edge(START, SPORTS_NODE)

        graph.add_edge(FINANCE_NODE, EDITOR_NODE)
        graph.add_edge(AI_NODE, EDITOR_NODE)
        graph.add_edge(SPORTS_NODE, EDITOR_NODE)
        graph.add_edge(EDITOR_NODE, INSTAGRAM_NODE)
        graph.add_edge(INSTAGRAM_NODE, END)

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
