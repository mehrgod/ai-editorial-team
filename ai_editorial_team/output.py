from ai_editorial_team.models import Story


def print_selected_story(story: Story, editorial_reason: str) -> None:
    """Print the Chief Editor decision in a readable command-line format."""
    print("\nSelected Story")
    print("==============")
    print(f"Domain: {story['domain']}")
    print(f"Headline: {story['headline']}")
    print(f"Summary: {story['summary']}")
    print(f"Story Reason: {story['reason']}")
    print(f"Editorial Reason: {editorial_reason}")
