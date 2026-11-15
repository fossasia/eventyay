import logging
import re

import asgiref
import channels
import requests
from django_scopes import scope

from eventyay.base.models import ChatEvent
from eventyay.base.services.chat import ChatService
from eventyay.celery_app import app
from eventyay.core.tasks import EventTask
from eventyay.features.live.channels import GROUP_CHAT
from eventyay.storage.external import fetch_preview_data


logger = logging.getLogger(__name__)


@app.task(base=EventTask)
def retrieve_preview_information(event, chat_event_id):
    # ``event`` is the Event (resolved by EventTask); ``chat_event_id`` is the chat message.
    # The message id must not be passed as ``event_id``: EventTask treats that as the Event id.
    with scope(event=event):
        chat_event = ChatEvent.objects.filter(id=chat_event_id, channel__event=event).first()
        if not chat_event:
            return
        stored = chat_event.content if isinstance(chat_event.content, dict) else {}
        body = stored.get("body")
        if stored.get("type") != "text" or not isinstance(body, str):
            return  # Deleted or changed to non-text content in the meantime

        match = re.search(r"(?P<url>https?://[^\s]+)", body)
        if not match:  # Message has changed in the meantime?
            return
        url = match.group("url")

        if url.endswith(")"):  # This is common enough to special-case it, I think
            url = url[:-1]

        try:
            preview_card = fetch_preview_data(url, event)
        except (requests.RequestException, ValueError, OSError):  # If this fails, just move on
            logger.exception("Could not build a link preview for chat event %s", chat_event.id)
            return
        if not preview_card:
            return

        # Only save if the message was not edited or deleted while the preview was fetched;
        # ``ChatService.update_event`` always sets ``edited``.
        content = {**stored, "preview_card": preview_card}
        unchanged = ChatEvent.objects.filter(pk=chat_event.pk)
        if chat_event.edited is None:
            unchanged = unchanged.filter(edited__isnull=True)
        else:
            unchanged = unchanged.filter(edited=chat_event.edited)
        if not unchanged.update(content=content):
            return

        event_data = asgiref.sync.async_to_sync(ChatService(event).create_event)(
            channel=chat_event.channel,
            event_type=chat_event.event_type,
            content=content,
            sender=chat_event.sender,
            replaces=chat_event.id,
        )
    channel_layer = channels.layers.get_channel_layer()
    asgiref.sync.async_to_sync(channel_layer.group_send)(
        GROUP_CHAT.format(channel=chat_event.channel_id),
        event_data,
    )
