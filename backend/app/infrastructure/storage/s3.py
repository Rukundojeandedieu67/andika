"""S3-compatible object storage. Credentials come from settings, never from code."""

from __future__ import annotations

from typing import Any

from app.infrastructure.storage.base import Storage, StorageError


class S3Storage(Storage):
    """Store media in a private or public S3-compatible bucket."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str = "",
        public_base_url: str = "",
        delivery: str = "private",
        signed_url_seconds: int = 3600,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url.strip() or None
        self.public_base_url = public_base_url.rstrip("/")
        self.delivery = delivery
        self.signed_url_seconds = signed_url_seconds
        self._client: Any = None

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self._validate_key(key)
        try:
            self._connection().put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError("The file could not be stored.") from exc

    def delete(self, key: str) -> None:
        self._validate_key(key)
        try:
            self._connection().delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageError("The stored file could not be removed.") from exc

    def exists(self, key: str) -> bool:
        self._validate_key(key)
        try:
            self._connection().head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", None)
            code = ""
            if isinstance(response, dict):
                code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageError("The stored file could not be read.") from exc
        return True

    def read(self, key: str) -> bytes:
        self._validate_key(key)
        try:
            response = self._connection().get_object(Bucket=self.bucket, Key=key)
            return bytes(response["Body"].read())
        except Exception as exc:
            raise StorageError("The stored file could not be read.") from exc

    def get_url(self, key: str) -> str:
        self._validate_key(key)
        if self.delivery == "public":
            if self.public_base_url:
                return f"{self.public_base_url}/{key}"
            if self.endpoint_url:
                return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        try:
            url = self._connection().generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=self.signed_url_seconds,
            )
        except Exception as exc:
            raise StorageError("A delivery URL could not be created.") from exc
        if not isinstance(url, str) or url == "":
            raise StorageError("A delivery URL could not be created.")
        return url

    def _connection(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise StorageError("Object storage is not available.") from exc
            self._client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
        return self._client

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not key
            or key.startswith("/")
            or ".." in key.split("/")
            or "\\" in key
            or "\0" in key
        ):
            raise StorageError("Invalid storage key.")
