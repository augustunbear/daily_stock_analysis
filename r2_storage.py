"""
Cloudflare R2 存储适配器
"""

import logging
import mimetypes
from pathlib import Path
from typing import Optional

import boto3

from config import Config

logger = logging.getLogger(__name__)


class R2Storage:
    def __init__(
        self,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        prefix: str = "",
        public_base_url: Optional[str] = None,
    ):
        self.endpoint = endpoint
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket = bucket
        self.prefix = self._normalize_prefix(prefix)
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
        )

    @classmethod
    def from_config(cls, config: Config) -> Optional["R2Storage"]:
        if not config.r2_endpoint:
            return None
        if not config.r2_access_key_id or not config.r2_secret_access_key:
            return None
        if not config.r2_bucket:
            return None
        return cls(
            endpoint=config.r2_endpoint,
            access_key_id=config.r2_access_key_id,
            secret_access_key=config.r2_secret_access_key,
            bucket=config.r2_bucket,
            prefix=config.r2_prefix or "",
            public_base_url=config.r2_public_base_url,
        )

    def upload_file(self, file_path: str, key: Optional[str] = None) -> Optional[str]:
        path = Path(file_path)
        object_key = key or self._build_key(path.name)
        content_type, _ = mimetypes.guess_type(path.name)
        extra_args = {"ContentType": content_type} if content_type else None

        try:
            if extra_args:
                self._client.upload_file(str(path), self.bucket, object_key, ExtraArgs=extra_args)
            else:
                self._client.upload_file(str(path), self.bucket, object_key)
            logger.info(f"R2 上传成功: {object_key}")
            return self._build_public_url(object_key)
        except Exception as e:
            logger.warning(f"R2 上传失败: {e}")
            return None

    def upload_text(
        self,
        content: str,
        key: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> Optional[str]:
        object_key = self._build_key(key)
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=content.encode("utf-8"),
                ContentType=content_type,
            )
            logger.info(f"R2 上传成功: {object_key}")
            return self._build_public_url(object_key)
        except Exception as e:
            logger.warning(f"R2 上传失败: {e}")
            return None

    def download_text(self, key: str) -> Optional[str]:
        object_key = self._build_key(key)
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=object_key)
            body = response.get("Body")
            if body is None:
                return None
            data = body.read()
            return data.decode("utf-8")
        except Exception as e:
            logger.debug(f"R2 下载失败: {object_key}, {e}")
            return None

    def exists(self, key: str) -> bool:
        object_key = self._build_key(key)
        try:
            self._client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except Exception:
            return False

    def _build_key(self, filename: str) -> str:
        return f"{self.prefix}{filename}" if self.prefix else filename

    def _build_public_url(self, object_key: str) -> Optional[str]:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{object_key}"

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        value = prefix.strip()
        if not value:
            return ""
        return value.rstrip("/") + "/"
