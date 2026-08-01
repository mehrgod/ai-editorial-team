import tempfile
import unittest
from pathlib import Path

from ai_editorial_team.infrastructure.image_storage.s3_image_storage import (
    S3ImageStorage,
    S3ImageStorageError,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.upload_calls = []
        self.presign_calls = []

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:
        self.upload_calls.append(
            {"Filename": Filename, "Bucket": Bucket, "Key": Key}
        )

    def generate_presigned_url(
        self, ClientMethod: str, Params: dict, ExpiresIn: int
    ) -> str:
        self.presign_calls.append(
            {
                "ClientMethod": ClientMethod,
                "Params": Params,
                "ExpiresIn": ExpiresIn,
            }
        )
        return "https://example.com/presigned-image.png"


class ExplodingUploadS3Client(FakeS3Client):
    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:
        raise RuntimeError("upload failed")


class ExplodingPresignS3Client(FakeS3Client):
    def generate_presigned_url(
        self, ClientMethod: str, Params: dict, ExpiresIn: int
    ) -> str:
        raise RuntimeError("presign failed")


class S3ImageStorageTests(unittest.TestCase):
    def test_upload_file_is_called_once_and_presigned_url_is_generated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")
            client = FakeS3Client()
            storage = S3ImageStorage(
                client=client,
                bucket_name="test-bucket",
                timestamp_factory=lambda: "20260731T120000000000Z",
            )

            result = storage.store(str(image_path))

            self.assertEqual(len(client.upload_calls), 1)
            self.assertEqual(client.upload_calls[0]["Filename"], str(image_path))
            self.assertEqual(client.upload_calls[0]["Bucket"], "test-bucket")
            self.assertTrue(
                client.upload_calls[0]["Key"].startswith(
                    "images/20260731T120000000000Z_"
                )
            )
            self.assertEqual(len(client.presign_calls), 1)
            self.assertEqual(
                client.presign_calls[0]["ClientMethod"],
                "get_object",
            )
            self.assertEqual(
                client.presign_calls[0]["Params"],
                {
                    "Bucket": "test-bucket",
                    "Key": client.upload_calls[0]["Key"],
                },
            )
            self.assertEqual(
                result,
                {
                    "object_key": client.upload_calls[0]["Key"],
                    "public_url": "https://example.com/presigned-image.png",
                },
            )

    def test_missing_local_file_produces_clear_infrastructure_error(self):
        storage = S3ImageStorage(
            client=FakeS3Client(),
            bucket_name="test-bucket",
        )

        with self.assertRaises(S3ImageStorageError) as context:
            storage.store("/tmp/missing-editorial.png")

        self.assertIn("Generated image file was not found", str(context.exception))

    def test_upload_failure_produces_clear_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")
            storage = S3ImageStorage(
                client=ExplodingUploadS3Client(),
                bucket_name="test-bucket",
            )

            with self.assertRaises(S3ImageStorageError) as context:
                storage.store(str(image_path))

            self.assertIn("S3 image upload failed", str(context.exception))

    def test_presigned_url_failure_produces_clear_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "editorial.png"
            image_path.write_bytes(b"fake-image")
            storage = S3ImageStorage(
                client=ExplodingPresignS3Client(),
                bucket_name="test-bucket",
            )

            with self.assertRaises(S3ImageStorageError) as context:
                storage.store(str(image_path))

            self.assertIn(
                "S3 presigned URL generation failed",
                str(context.exception),
            )
