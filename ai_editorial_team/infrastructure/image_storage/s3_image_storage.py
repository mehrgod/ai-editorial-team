from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Callable, Protocol
from uuid import uuid4

from dotenv import load_dotenv

from ai_editorial_team.domain.models import StoredImage
from ai_editorial_team.domain.ports import ImageStorage


PRESIGNED_URL_EXPIRATION_SECONDS = 15 * 60
S3_IMAGE_PREFIX = "images"


class S3ImageStorageError(RuntimeError):
    """Raised when S3 image storage fails."""


class S3ImageStorageConfigurationError(S3ImageStorageError):
    """Raised when required S3 configuration is missing."""


class S3Client(Protocol):
    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:
        ...

    def generate_presigned_url(
        self, ClientMethod: str, Params: dict, ExpiresIn: int
    ) -> str:
        ...


@dataclass(frozen=True)
class S3ImageStorageConfig:
    aws_region: str
    bucket_name: str

    @classmethod
    def from_env(cls) -> "S3ImageStorageConfig":
        load_dotenv()

        aws_region = os.environ.get("AWS_REGION")
        bucket_name = os.environ.get("S3_BUCKET_NAME")

        missing = [
            name
            for name, value in [
                ("AWS_REGION", aws_region),
                ("S3_BUCKET_NAME", bucket_name),
            ]
            if not value
        ]
        if missing:
            raise S3ImageStorageConfigurationError(
                "Missing required S3 image storage configuration: "
                + ", ".join(missing)
            )

        return cls(
            aws_region=aws_region,
            bucket_name=bucket_name,
        )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class S3ImageStorage(ImageStorage):
    """Stores generated images in a private S3 bucket."""

    client: S3Client
    bucket_name: str
    key_prefix: str = S3_IMAGE_PREFIX
    presigned_url_expiration_seconds: int = PRESIGNED_URL_EXPIRATION_SECONDS
    timestamp_factory: Callable[[], str] = _utc_timestamp

    def store(self, local_file_path: str) -> StoredImage:
        image_path = Path(local_file_path)
        if not image_path.is_file():
            raise S3ImageStorageError(
                f"Generated image file was not found: {image_path}"
            )

        object_key = self._object_key(image_path)

        try:
            self.client.upload_file(
                Filename=str(image_path),
                Bucket=self.bucket_name,
                Key=object_key,
            )
        except Exception as exc:
            raise S3ImageStorageError(
                f"S3 image upload failed for {image_path}: {exc}"
            ) from exc

        try:
            public_url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=self.presigned_url_expiration_seconds,
            )
        except Exception as exc:
            raise S3ImageStorageError(
                f"S3 presigned URL generation failed for {object_key}: {exc}"
            ) from exc

        if not public_url:
            raise S3ImageStorageError(
                f"S3 presigned URL generation returned no URL for {object_key}."
            )

        return {
            "object_key": object_key,
            "public_url": public_url,
        }

    def _object_key(self, image_path: Path) -> str:
        extension = image_path.suffix or ".png"
        return (
            f"{self.key_prefix}/{self.timestamp_factory()}_"
            f"{uuid4().hex}{extension}"
        )


def create_s3_image_storage_from_env() -> S3ImageStorage:
    config = S3ImageStorageConfig.from_env()

    import boto3

    client = boto3.client(
        "s3",
        region_name=config.aws_region,
    )
    return S3ImageStorage(
        client=client,
        bucket_name=config.bucket_name,
    )
