from ai_editorial_team.application.workflow import EditorialWorkflow


def run_cli(workflow: EditorialWorkflow) -> None:
    """Run the editorial workflow and print ranked Instagram content."""
    result = workflow.run()
    instagram_story_contents = result["instagram_story_contents"]

    for story_content in instagram_story_contents:
        story = story_content["story"]
        print(f"\nRank {story_content['rank']}")
        print("======")
        print(f"Domain: {story['domain']}")
        print(f"Headline: {story['headline']}")
        print(f"Editorial Reason: {story_content['editorial_reason']}")
        print(
            "Instagram Caption: "
            f"{story_content['instagram_content']['caption']}"
        )
        print(f"Image Prompt: {story_content['image_prompt']['image_prompt']}")
        print(f"Generated Image: {story_content['generated_image']['file_path']}")
