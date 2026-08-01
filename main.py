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
    from ai_editorial_team.infrastructure.content.openai_instagram_content_agent import (
        InstagramContentAgent,
    )
    from ai_editorial_team.infrastructure.content.openai_image_prompt_agent import (
        ImagePromptAgent,
    )
    from ai_editorial_team.infrastructure.content.openai_x_content_agent import (
        XContentAgent,
    )
    from ai_editorial_team.infrastructure.image_generation.openai_image_generator import (
        OpenAIImageGenerator,
    )
    from ai_editorial_team.infrastructure.image_storage.s3_image_storage import (
        S3ImageStorageError,
        create_s3_image_storage_from_env,
    )
    from ai_editorial_team.infrastructure.publishing.instagram_publisher import (
        InstagramPublishingError,
        create_instagram_publisher_from_env,
    )
    from ai_editorial_team.infrastructure.publishing.x_publisher import (
        XPublishingError,
        create_x_publisher_from_env,
    )
    from ai_editorial_team.infrastructure.research.rss_agents import (
        RssFeedError,
        create_ai_research_agent,
        create_finance_research_agent,
        create_sports_research_agent,
    )
    from ai_editorial_team.presentation.cli import run_cli
    from ai_editorial_team.infrastructure.editor.openai_chief_editor import (
        LLMChiefEditor,
    )
    from ai_editorial_team.infrastructure.openai.client import (
        create_openai_client_bundle_from_env,
    )
    from ai_editorial_team.infrastructure.openai.config import (
        OpenAIInfrastructureError,
    )

    try:
        openai_bundle = create_openai_client_bundle_from_env()
        workflow = EditorialWorkflow(
            finance_research_agent=create_finance_research_agent(),
            ai_research_agent=create_ai_research_agent(),
            sports_research_agent=create_sports_research_agent(),
            chief_editor=LLMChiefEditor(
                client=openai_bundle.client,
                model=openai_bundle.model,
            ),
            instagram_content_agent=InstagramContentAgent(
                client=openai_bundle.client,
                model=openai_bundle.model,
            ),
            x_content_agent=XContentAgent(
                client=openai_bundle.client,
                model=openai_bundle.model,
            ),
            image_prompt_agent=ImagePromptAgent(
                client=openai_bundle.client,
                model=openai_bundle.model,
            ),
            image_generator=OpenAIImageGenerator(
                client=openai_bundle.client,
                model=openai_bundle.image_model,
            ),
            image_storage=create_s3_image_storage_from_env(),
            instagram_publisher=create_instagram_publisher_from_env(),
            x_publisher=create_x_publisher_from_env(),
        )
        run_cli(workflow)
    except (
        RssFeedError,
        InstagramPublishingError,
        OpenAIInfrastructureError,
        S3ImageStorageError,
        XPublishingError,
    ) as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
