import logging
from multiprocessing import cpu_count, pool

import requests
from django.core.management.base import BaseCommand
from lxml import etree

from eventyay.base.models import BBBServer
from eventyay.base.services.bbb import get_url


logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = (5, 30)


class Command(BaseCommand):
    help = "Update load balancing costs of BBB servers"

    def _update_cost(self, server: BBBServer):
        try:
            meetings_url = get_url("getMeetings", {}, server.url, server.secret)
            r = requests.get(meetings_url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            cost = 0

            root = etree.fromstring(r.text)
            if root.xpath("returncode")[0].text != "SUCCESS":
                raise ValueError("Meetings could not be fetched: " + r.text)

            # Every meeting has a base cost of 10. Video cost is estimated as
            # 10 * senders * recipients, and audio as senders * recipients.
            for meet in root.xpath("meetings/meeting"):
                participants = int(meet.xpath("participantCount")[0].text)
                voice_users = int(meet.xpath("voiceParticipantCount")[0].text)
                video_users = int(meet.xpath("videoCount")[0].text)

                cost += (
                    10 + 10 * participants * video_users + participants * voice_users
                )

            server.cost = cost
            server.save(update_fields=["cost"])

        except Exception:
            logger.exception(f"Could not query BBB server {server.id} / {server.url}")

    def handle(self, *args, **options):
        p = pool.ThreadPool(processes=cpu_count())
        p.map(self._update_cost, BBBServer.objects.filter(active=True))
