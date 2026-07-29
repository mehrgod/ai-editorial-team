from ai_editorial_team.application.workflow import EditorialWorkflow


def run_cli(workflow: EditorialWorkflow) -> None:
    """Run the editorial workflow and print its selected story."""
    result = workflow.run()
    story = result["selected_story"]
    editorial_reason = result["editorial_reason"]
    instagram_content = result["instagram_content"]
    x_content = result["x_content"]
    image_prompt = result["image_prompt"]
    generated_image = result["generated_image"]

    print("\nSelected Story")
    print("==============")
    print(f"Domain: {story['domain']}")
    print(f"Headline: {story['headline']}")
    print(f"Summary: {story['summary']}")
    print(f"Story Reason: {story['reason']}")
    print(f"Editorial Reason: {editorial_reason}")
    print("\nInstagram Caption")
    print("=================")
    print(instagram_content["caption"])
    print("\nX Post")
    print("======")
    print(x_content["post"])
    print("\nImage Prompt")
    print("============")
    print(image_prompt["image_prompt"])
    print("\nGenerated Image")
    print("===============")
    print(f"Path: {generated_image['file_path']}")
