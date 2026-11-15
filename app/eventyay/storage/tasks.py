import logging
import re

import asgiref
import channels
import requests

from eventyay.celery_app import app
from eventyay.base.models import ChatEvent
from eventyay.base.services.chat import ChatService
from eventyay.core.tasks import EventTask
from eventyay.features.live.channels import GROUP_CHAT
from eventyay.storage.external import fetch_preview_data

logger = logging.getLogger(__name__)


@app.task(base=EventTask)
def retrieve_preview_information(event, chat_event_id):
    # ``event`` is the Event (resolved by EventTask); ``chat_event_id`` is the chat message.
    # The message id must not be passed as ``event_id``: EventTask treats that as the Event id.
    chat_event = ChatEvent.objects.filter(id=chat_event_id, channel__event=event).first()
    if not chat_event:
        return

    match = re.search(r"(?P<url>https?://[^\s]+)", chat_event.content.get("body"))
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

    if preview_card:
        chat_event.content["preview_card"] = preview_card
        chat_event.save()

        event_data = asgiref.sync.async_to_sync(ChatService(event).create_event)(
            channel=chat_event.channel,
            event_type=chat_event.event_type,
            content=chat_event.content,
            sender=chat_event.sender,
            replaces=chat_event.id,
        )
        channel_layer = channels.layers.get_channel_layer()
        asgiref.sync.async_to_sync(channel_layer.group_send)(
            GROUP_CHAT.format(channel=chat_event.channel_id),
            event_data,
        )
