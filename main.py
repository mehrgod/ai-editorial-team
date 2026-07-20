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

    from ai_editorial_team.output import print_selected_story
    from ai_editorial_team.workflow import build_editorial_graph

    app = build_editorial_graph()
    result = app.invoke({"stories": []})
    print_selected_story(result["selected_story"], result["editorial_reason"])


if __name__ == "__main__":
    main()
