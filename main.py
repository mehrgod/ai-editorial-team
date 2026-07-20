from ai_editorial_team.output import print_selected_story
from ai_editorial_team.workflow import build_editorial_graph


def main() -> None:
    """Run the Milestone 1 editorial workflow."""
    app = build_editorial_graph()
    result = app.invoke({"stories": []})
    print_selected_story(result["selected_story"], result["editorial_reason"])


if __name__ == "__main__":
    main()
