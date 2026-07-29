from dataclasses import dataclass

from openai import OpenAI

from ai_editorial_team.infrastructure.openai.config import OpenAIConfig


@dataclass(frozen=True)
class OpenAIClientBundle:
    """Configured OpenAI SDK client and model shared by OpenAI-backed agents."""

    client: OpenAI
    model: str
    image_model: str


def create_openai_client_bundle(
    config: OpenAIConfig,
) -> OpenAIClientBundle:
    return OpenAIClientBundle(
        client=OpenAI(api_key=config.api_key),
        model=config.model,
        image_model=config.image_model,
    )


def create_openai_client_bundle_from_env() -> OpenAIClientBundle:
    return create_openai_client_bundle(OpenAIConfig.from_env())
