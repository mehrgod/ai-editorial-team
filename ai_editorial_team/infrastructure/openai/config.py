from dataclasses import dataclass
import os

from dotenv import load_dotenv


DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"


class OpenAIInfrastructureError(RuntimeError):
    """Base error for shared OpenAI infrastructure failures."""


class OpenAIConfigurationError(OpenAIInfrastructureError):
    """Raised when required OpenAI configuration is missing."""


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str = DEFAULT_OPENAI_MODEL
    image_model: str = DEFAULT_OPENAI_IMAGE_MODEL

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is not set. Set it in your environment before "
                "running the application."
            )

        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
            image_model=(
                os.environ.get("OPENAI_IMAGE_MODEL")
                or DEFAULT_OPENAI_IMAGE_MODEL
            ),
        )
