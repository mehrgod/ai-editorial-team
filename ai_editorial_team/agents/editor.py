from ai_editorial_team.models import EditorialDecision, EditorialState


def chief_editor_agent(state: EditorialState) -> EditorialDecision:
    """Select the story of the day from the research candidates."""
    stories = state["stories"]
    if not stories:
        raise ValueError("Chief Editor Agent requires at least one candidate story.")

    # Milestone 1 keeps the decision deterministic. Later milestones can replace
    # this with LLM evaluation while preserving the same graph contract.
    selected_story = next(
        (story for story in stories if story["domain"] == "Artificial Intelligence"),
        stories[0],
    )

    return {
        "selected_story": selected_story,
        "editorial_reason": (
            "Selected because the AI story has the broadest strategic impact "
            "for a technology-focused audience."
        ),
    }
