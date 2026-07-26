import sys


MIN_PYTHON_VERSION = (3, 10)


def main() -> None:
    """Run the Milestone 1 editorial workflow."""
    if sys.version_info < MIN_PYTHON_VERSION:
        current_version = ".".join(str(part) for part in sys.version_info[:3])
        required_version = ".".join(str(part) for part in MIN_PYTHON_VERSION)
        raise SystemExit(
            "AI Editorial Team requires Python "
            f"{required_version}+ because LangGraph requires Python "
            f"{required_version}+. Current interpreter: Python {current_version}."
        )

    from ai_editorial_team.application.workflow import EditorialWorkflow
    from ai_editorial_team.domain.services import DeterministicChiefEditor
    from ai_editorial_team.infrastructure.research.rss_agents import (
        RssFeedError,
        create_ai_research_agent,
        create_finance_research_agent,
        create_sports_research_agent,
    )
    from ai_editorial_team.presentation.cli import run_cli

    workflow = EditorialWorkflow(
        finance_research_agent=create_finance_research_agent(),
        ai_research_agent=create_ai_research_agent(),
        sports_research_agent=create_sports_research_agent(),
        chief_editor=DeterministicChiefEditor(),
    )
    try:
        run_cli(workflow)
    except RssFeedError as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
