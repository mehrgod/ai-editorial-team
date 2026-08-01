from dataclasses import dataclass
import os

from dotenv import load_dotenv


DEFAULT_GRAPH_API_VERSION = "v23.0"


class PublishingInfrastructureError(RuntimeError):
    """Base error for publishing infrastructure failures."""


class PublishingConfigurationError(PublishingInfrastructureError):
    """Raised when publishing configuration is missing or invalid."""


@dataclass(frozen=True)
class InstagramPublishingConfig:
    instagram_professional_account_id: str
    meta_access_token: str
    graph_api_version: str = DEFAULT_GRAPH_API_VERSION

    @classmethod
    def from_env(cls) -> "InstagramPublishingConfig":
        load_dotenv()

        instagram_professional_account_id = os.environ.get(
            "INSTAGRAM_PROFESSIONAL_ACCOUNT_ID"
        )
        meta_access_token = os.environ.get("META_ACCESS_TOKEN")
        graph_api_version = (
            os.environ.get("GRAPH_API_VERSION") or DEFAULT_GRAPH_API_VERSION
        )

        missing = [
            name
            for name, value in [
                ("INSTAGRAM_PROFESSIONAL_ACCOUNT_ID", instagram_professional_account_id),
                ("META_ACCESS_TOKEN", meta_access_token),
            ]
            if not value
        ]
        if missing:
            raise PublishingConfigurationError(
                "Missing required Instagram publishing configuration: "
                + ", ".join(missing)
            )

        return cls(
            instagram_professional_account_id=instagram_professional_account_id,
            meta_access_token=meta_access_token,
            graph_api_version=graph_api_version,
        )
