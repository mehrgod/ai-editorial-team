from ai_editorial_team.application.workflow import EditorialWorkflow


def run_cli(workflow: EditorialWorkflow) -> None:
    """Run the editorial workflow and print the ranked stories."""
    result = workflow.run()
    ranked_stories = result["ranked_stories"]

    print("\nRanked Stories")
    print("==============")
    for ranked_story in ranked_stories:
        story = ranked_story["story"]
        print(
            f"\n{ranked_story['rank']}. "
            f"[{story['domain']}] {story['headline']}"
        )
        print(f"   Editorial Reason: {ranked_story['editorial_reason']}")
