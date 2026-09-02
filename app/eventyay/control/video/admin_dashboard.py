from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import (
    BBBServer,
    JanusServer,
    JitsiServer,
    StreamingServer,
    TurnServer,
)


@dataclass(frozen=True)
class VideoServerConfig:
    model: object
    label: str
    list_url_name: str
    update_url_name: str
    order_by: str
    display_attr: str
    action_prefix: str


VIDEO_SERVER_CONFIGS = {
    "bbb": VideoServerConfig(
        model=BBBServer,
        label=_("BBB"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:bbbserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="bbbserver",
    ),
    "janus": VideoServerConfig(
        model=JanusServer,
        label=_("Janus"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:janusserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="janusserver",
    ),
    "jitsi": VideoServerConfig(
        model=JitsiServer,
        label=_("Jitsi"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:jitsiserver.update",
        order_by="url",
        display_attr="url",
        action_prefix="jitsiserver",
    ),
    "turn": VideoServerConfig(
        model=TurnServer,
        label=_("TURN"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:turnserver.update",
        order_by="hostname",
        display_attr="hostname",
        action_prefix="turnserver",
    ),
    "streaming": VideoServerConfig(
        model=StreamingServer,
        label=_("Streaming"),
        list_url_name="eventyay_admin:video_admin:settings",
        update_url_name="eventyay_admin:video_admin:streamingserver.update",
        order_by="name",
        display_attr="name",
        action_prefix="streamingserver",
    ),
}


def get_video_server_config(server_type):
    return VIDEO_SERVER_CONFIGS.get(server_type)


def get_video_server_dashboard_rows():
    from eventyay.base.settings import GlobalSettingsObject
    global_settings = GlobalSettingsObject().settings

    rows = []
    for server_type, config in VIDEO_SERVER_CONFIGS.items():
        queryset = config.model.objects.all().order_by(config.order_by)
        has_events_exclusive = any(
            field.name == "events_exclusive" for field in config.model._meta.get_fields()
        )
        if has_events_exclusive:
            queryset = queryset.prefetch_related("events_exclusive")

        # Map server_type to the corresponding global setting key
        setting_key = None
        if server_type == "jitsi":
            setting_key = "video_jitsi_enabled"
        elif server_type == "bbb":
            setting_key = "video_bbb_enabled"
        elif server_type == "janus":
            setting_key = "video_janus_enabled"
        elif server_type == "streaming":
            setting_key = "video_streaming_enabled"
            
        feature_enabled = True
        if setting_key:
            feature_enabled = global_settings.get(setting_key, True)

        for server in queryset:
            active = bool(server.active)
            
            if not feature_enabled:
                status_str = str(_("Disabled Globally"))
            else:
                status_str = str(_("Active")) if active else str(_("Inactive"))

            rows.append(
                {
                    "server_type": server_type,
                    "type_label": config.label,
                    "name": getattr(server, config.display_attr),
                    "events_exclusive": list(server.events_exclusive.all()) if has_events_exclusive else None,
                    "edit_url": reverse(
                        config.update_url_name, kwargs={"pk": server.pk}
                    ),
                    "list_url": reverse(config.list_url_name) + f"?tab={server_type}",
                    "toggle_url": reverse(
                        "eventyay_admin:video_admin:server.toggle-active",
                        kwargs={"server_type": server_type, "pk": server.pk},
                    ),
                    "active": active,
                    "feature_enabled": feature_enabled,
                    "status": status_str,
                }
            )
    return rows
