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
        print(f"S3 Object Key: {story_content['stored_image']['object_key']}")
        print(f"Presigned Image URL: {story_content['stored_image']['public_url']}")

    publication = result["instagram_publication"]
    print("\nInstagram Carousel Published")
    print("============================")
    print(f"Platform: {publication['platform']}")
    print(f"Publication ID: {publication['publication_id']}")
    print(f"URL: {publication['publication_url']}")

    print("\nX Post")
    print("======")
    print(result["x_content"]["post"])

    x_publication = result["x_publication"]
    print("\nX Published")
    print("===========")
    print(f"Platform: {x_publication['platform']}")
    print(f"Publication ID: {x_publication['publication_id']}")
    print(f"URL: {x_publication['publication_url']}")
