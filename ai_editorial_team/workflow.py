from langgraph.graph import END, START, StateGraph

from ai_editorial_team.agents.editor import chief_editor_agent
from ai_editorial_team.agents.research import (
    ai_research_agent,
    finance_research_agent,
    sports_research_agent,
)
from ai_editorial_team.models import EditorialState


FINANCE_NODE = "Finance Research Agent"
AI_NODE = "AI Research Agent"
SPORTS_NODE = "Sports Research Agent"
EDITOR_NODE = "Chief Editor Agent"


def build_editorial_graph():
    """Build and compile the Milestone 1 LangGraph workflow."""
    graph = StateGraph(EditorialState)

    graph.add_node(FINANCE_NODE, finance_research_agent)
    graph.add_node(AI_NODE, ai_research_agent)
    graph.add_node(SPORTS_NODE, sports_research_agent)
    graph.add_node(EDITOR_NODE, chief_editor_agent)

    # Fan out to the three research agents, then fan in to the Chief Editor.
    graph.add_edge(START, FINANCE_NODE)
    graph.add_edge(START, AI_NODE)
    graph.add_edge(START, SPORTS_NODE)

    graph.add_edge(FINANCE_NODE, EDITOR_NODE)
    graph.add_edge(AI_NODE, EDITOR_NODE)
    graph.add_edge(SPORTS_NODE, EDITOR_NODE)
    graph.add_edge(EDITOR_NODE, END)

    return graph.compile()
