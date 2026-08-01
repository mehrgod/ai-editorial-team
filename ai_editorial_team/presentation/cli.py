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
    stored_image = result["stored_image"]
    instagram_publication_result = result["instagram_publication_result"]
    x_publication_result = result["x_publication_result"]

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
    print("\nStored Image")
    print("============")
    print(f"S3 Key: {stored_image['object_key']}")
    print(f"URL: {stored_image['public_url']}")
    print("\nInstagram Published")
    print("===================")
    print(f"Platform: {instagram_publication_result['platform']}")
    print(
        "Publication ID: "
        f"{instagram_publication_result['publication_id']}"
    )
    print(f"URL: {instagram_publication_result['publication_url']}")
    print("\nX Published")
    print("===========")
    print(f"Platform: {x_publication_result['platform']}")
    print(f"Publication ID: {x_publication_result['publication_id']}")
    print(f"URL: {x_publication_result['publication_url']}")
