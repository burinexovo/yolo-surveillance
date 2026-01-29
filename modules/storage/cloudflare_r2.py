# modules/storage/cloudflare_r2.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

import boto3
from botocore.client import Config


@dataclass(frozen=True)
class R2Config:
    access_key: str
    secret_key: str
    bucket: str
    endpoint: str
    public_url: str


class CloudflareR2:
    def __init__(self, cfg: R2Config):
        self.cfg = cfg

    def get_client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.cfg.endpoint,
            aws_access_key_id=self.cfg.access_key,
            aws_secret_access_key=self.cfg.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def list_files(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        s3 = self.get_client()
        return s3.list_objects_v2(
            Bucket=self.cfg.bucket,
            Prefix=prefix or ""
        ).get("Contents", [])

    def upload_file(self, filepath: Union[str, Path], key: str) -> str:
        """
        上傳檔案到指定 key，回傳 public url
        """
        filepath = Path(filepath)
        s3 = self.get_client()

        s3.upload_file(
            Filename=str(filepath),
            Bucket=self.cfg.bucket,
            Key=key,
            ExtraArgs={"ACL": "public-read"},
        )
        return f"{self.cfg.public_url}/{key}"

    def upload_bytes(self, data: bytes, key: str, content_type: Optional[str] = None) -> str:
        s3 = self.get_client()
        extra = {"ACL": "public-read"}
        if content_type:
            extra["ContentType"] = content_type

        s3.put_object(
            Bucket=self.cfg.bucket,
            Key=key,
            Body=data,
            **extra,
        )
        return f"{self.cfg.public_url}/{key}"

    def file_exists(self, key: str) -> bool:
        s3 = self.get_client()
        try:
            s3.head_object(Bucket=self.cfg.bucket, Key=key)
            return True
        except Exception:
            return False

    def folder_exists(self, prefix: str) -> bool:
        files = self.list_files(prefix)
        return len(files) > 0

    def create_folder(self, prefix: str) -> None:
        if not prefix.endswith("/"):
            prefix += "/"
        s3 = self.get_client()
        s3.put_object(Bucket=self.cfg.bucket, Key=prefix)

    def delete_file(self, key: str) -> None:
        s3 = self.get_client()
        s3.delete_object(Bucket=self.cfg.bucket, Key=key)
