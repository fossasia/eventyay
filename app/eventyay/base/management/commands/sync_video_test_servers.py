"""
Management command: sync_video_test_servers
Synchronizes local development video servers (Jitsi, BBB, Janus, Coturn) based on VIDEO_SERVER_TEST_MODE.

Usage:
    python manage.py sync_video_test_servers --enable
    python manage.py sync_video_test_servers --disable
"""

import os

from django.core.management.base import BaseCommand

from eventyay.base.models import (
    BBBServer,
    JanusServer,
    JitsiServer,
    TurnServer,
)


class Command(BaseCommand):
    help = "Enable or disable local video test servers and synchronize database records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enable",
            action="store_true",
            help="Seed and activate local video test servers (BBB, Janus, Jitsi, Coturn).",
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Deactivate local video test servers so rooms gracefully display offline notices.",
        )

    def handle(self, *args, **options):
        if options["enable"]:
            self.enable_servers()
        elif options["disable"]:
            self.disable_servers()
        else:
            self.stdout.write(self.style.WARNING("Please specify either --enable or --disable."))

    def enable_servers(self):
        self.stdout.write("--- Enabling Local Video Test Servers ---")

        # 1. BigBlueButton Server
        bbb_url = os.environ.get("BBB_URL", "https://test-install.blindsidenetworks.com/bigbluebutton/api")
        bbb_secret = os.environ.get("BBB_SECRET", "8cd8ef52e8e101574e400365b55e11a6")
        bbb_obj, _ = BBBServer.objects.update_or_create(
            url=bbb_url,
            defaults={
                "secret": bbb_secret,
                "active": True,
                "rooms_only": False,
                "cost": 0,
            },
        )
        self.stdout.write(f"✓ BBB Server active: {bbb_obj.url}")

        # 2. Janus Gateway Server
        janus_key = os.environ.get("JANUS_ROOM_CREATE_KEY", "janusrocks")
        janus_obj, _ = JanusServer.objects.update_or_create(
            url="ws://localhost:8188",
            defaults={
                "room_create_key": janus_key,
                "active": True,
            },
        )
        self.stdout.write(f"✓ Janus Server active: {janus_obj.url}")

        # 3. Jitsi Meet Server
        jitsi_app_id = os.environ.get("JWT_APP_ID", "eventyay")
        jitsi_app_secret = os.environ.get("JWT_APP_SECRET", "eventyay_jitsi_jwt_secret_dev_2026")
        jitsi_url = os.environ.get("PUBLIC_URL", "http://localhost:8002")
        jitsi_obj, _ = JitsiServer.objects.update_or_create(
            url=jitsi_url,
            defaults={
                "app_id": jitsi_app_id,
                "app_secret": jitsi_app_secret,
                "key_id": "",
                "active": True,
            },
        )
        self.stdout.write(f"✓ Jitsi Server active: {jitsi_obj.url}")

        # 4. Coturn TURN Server
        turn_secret = os.environ.get("COTURN_AUTH_SECRET", "eventyay_coturn_secret")
        turn_obj, _ = TurnServer.objects.update_or_create(
            hostname="localhost:3478",
            defaults={
                "auth_secret": turn_secret,
                "active": True,
            },
        )
        self.stdout.write(f"✓ TURN Server active: {turn_obj.hostname}")

        self.stdout.write(self.style.SUCCESS("✓ All local video test servers enabled and synchronized successfully!"))

    def disable_servers(self):
        self.stdout.write("--- Deactivating Local Video Test Servers ---")
        bbb_url = os.environ.get("BBB_URL", "https://test-install.blindsidenetworks.com/bigbluebutton/api")
        bbb_count = BBBServer.objects.filter(
            url__in=[bbb_url, "http://localhost:8090/bigbluebutton/api"],
            active=True,
        ).update(active=False)
        janus_count = JanusServer.objects.filter(url__contains="localhost", active=True).update(active=False)
        jitsi_count = JitsiServer.objects.filter(url__contains="localhost", active=True).update(active=False)
        turn_count = TurnServer.objects.filter(hostname__contains="localhost", active=True).update(active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Deactivated local servers: {bbb_count} BBB, {janus_count} Janus, "
                f"{jitsi_count} Jitsi, {turn_count} TURN."
            )
        )
