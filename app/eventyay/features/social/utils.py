import logging
import os
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.db import DatabaseError

from eventyay.base.models import User
from eventyay.base.models.storage_model import StoredFile

logger = logging.getLogger(__name__)

# Timeout for outbound requests to external services (seconds)
EXTERNAL_REQUEST_TIMEOUT = 10


def update_user_profile_from_social(
    user: User, network, *, name, url, avatar_url=None, avatar_media_type=None
):
    if name and not user.profile.get("display_name"):
        user.profile["display_name"] = name

    if avatar_url and not user.profile.get("avatar", {}).get("url"):
        content_types = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "gif": "image/gif",
        }
        # Extract extension safely from URL path, avoiding query params or malformed URLs
        path = urlparse(avatar_url).path
        ext = os.path.splitext(path)[1].lstrip('.')
        if not ext or '/' in ext or '?' in ext:
            ext = 'png'  # safe default for ambiguous/malformed URLs
        try:
            r = requests.get(avatar_url, timeout=EXTERNAL_REQUEST_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException:
            logger.exception("Could not download avatar")
        else:
            try:
                c = ContentFile(r.content)
                sf = StoredFile.objects.create(
                    event=user.event,
                    user=user,
                    filename=f"avatar.{ext}",
                    type=avatar_media_type or content_types.get(ext.lower(), "image/png"),
                    public=True,
                )
                sf.file.save(f"avatar.{ext}", c)
            except (DatabaseError, OSError, ValueError):
                logger.exception("Could not save avatar")
            else:
                user.profile["avatar"] = {
                    "url": sf.file.url,
                }

    if url:
        user.profile.setdefault("fields", {})

        for field in user.event.config.get("profile_fields", []):
            if field.get("type") == "link" and field.get("network") == network:
                user.profile["fields"][field["id"]] = url

    user.save(update_fields=["profile"])
