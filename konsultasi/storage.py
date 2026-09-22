"""
Profile-picture storage on Supabase Storage (S3-compatible endpoint).

Uploads are private-signed via AWS SigV4 using the S3 access key, but the
'pfp' bucket is public, so the stored URL is directly fetchable by browsers.
"""

import logging
import uuid
from urllib.parse import quote

from botocore.client import Config
from django.conf import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_CHAT_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


class AvatarError(Exception):
    """Raised when an avatar can't be stored."""


def _s3_client():
    from boto3 import client as boto3_client

    return boto3_client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=30),
    )


def _put_object(key: str, upload, content_type: str) -> str:
    """Upload a file to S3 and return its public URL."""
    try:
        _s3_client().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=upload.read(),
            ContentType=content_type,
        )
    except Exception as exc:
        logger.exception("S3 upload failed: %s", exc)
        raise AvatarError("Gagal mengupload foto. Silakan coba lagi.") from exc
    return f"{settings.S3_PUBLIC_BASE_URL}/{quote(key)}"


def upload_avatar(user_id: int, upload) -> str:
    """
    Upload an avatar file for a user and return its public URL.

    Raises AvatarError on validation or storage failure.
    """
    if not upload or not getattr(upload, "name", ""):
        raise AvatarError("No avatar file provided.")

    content_type = getattr(upload, "content_type", "") or ""
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise AvatarError("Only JPG, PNG, WebP, or GIF images are allowed.")

    if upload.size > MAX_AVATAR_BYTES:
        raise AvatarError("Avatar maksimal 5 MB.")

    key = f"avatars/user-{user_id}/{uuid.uuid4().hex}{ext}"
    return _put_object(key, upload, content_type)


def upload_chat_image(user_id: int, data: bytes, content_type: str) -> str:
    """
    Upload an image attached to a consultation message and return its public URL.

    Raises AvatarError on validation or storage failure.
    """
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise AvatarError("Only JPG, PNG, WebP, or GIF images are allowed.")

    if len(data) > MAX_CHAT_IMAGE_BYTES:
        raise AvatarError("Foto maksimal 10 MB.")

    key = f"chat/user-{user_id}/{uuid.uuid4().hex}{ext}"
    try:
        _s3_client().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except Exception as exc:
        logger.exception("S3 chat image upload failed: %s", exc)
        raise AvatarError("Gagal mengupload foto. Silakan coba lagi.") from exc
    return f"{settings.S3_PUBLIC_BASE_URL}/{quote(key)}"


def delete_avatar(avatar_url: str) -> None:
    """Best-effort deletion of the object behind a public avatar URL."""
    if not avatar_url:
        return
    try:
        key = avatar_url.split(settings.S3_PUBLIC_BASE_URL + "/", 1)[1]
    except IndexError:
        return
    try:
        _s3_client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    except Exception as exc:
        logger.warning("Avatar delete failed (ignored): %s", exc)