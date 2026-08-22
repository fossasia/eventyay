from datetime import datetime
from functools import reduce
from operator import or_

from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay.base.exporter import ListExporter


BROADCAST_MODULE_TYPES = {
    "livestream.native",
    "livestream.youtube",
    "livestream.iframe",
}

YOUTUBE_BOOLEAN_OPTIONS = (
    ("start_muted", "startMuted"),
    ("youtube_privacy_enhanced", "enablePrivacyEnhancedMode"),
    ("youtube_loop", "loop"),
    ("youtube_modest_branding", "modestBranding"),
    ("youtube_hide_controls", "hideControls"),
    ("youtube_no_related", "noRelated"),
    ("youtube_disable_keyboard", "disableKb"),
    ("youtube_show_info", "showInfo"),
)


def _value(data, *keys):
    for key in keys:
        if isinstance(data, dict) and data.get(key) not in (None, ""):
            return data.get(key)
    return ""


def _cell(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class VideoRoomBroadcastConfigurationExporter(ListExporter):
    @property
    def verbose_name(self) -> str:
        return _("Video room broadcast configuration")

    @property
    def identifier(self) -> str:
        return "video_room_broadcast_configuration"

    def get_filename(self):
        return f"{self.event.slug}-video-room-broadcast-configuration"

    @cached_property
    def headers(self):
        return [
            "row_type",
            "room_id",
            "room_name",
            "room_type",
            "module_type",
            "playback_mode",
            "hls_url",
            "iframe_url",
            "youtube_id",
            "subtitles_url",
            "stream_offline_image",
            "mux_env_key",
            *[label for label, _key in YOUTUBE_BOOLEAN_OPTIONS],
            "alternative_label",
            "alternative_hls_url",
            "language",
            "language_youtube_id",
            "language_url",
            "language_use_video",
            "stream_schedule_id",
            "stream_schedule_title",
            "stream_schedule_url",
            "stream_schedule_start_time",
            "stream_schedule_end_time",
            "stream_schedule_type",
            "stream_schedule_language",
            "stream_schedule_use_video",
        ]

    def iterate_list(self, form_data):
        yield self.headers
        for room in self._rooms():
            room_data = self._room_data(room)
            yield self._row(room_data, row_type="room_config")
            for module in room.module_config or []:
                if module.get("type") not in BROADCAST_MODULE_TYPES:
                    continue
                yield from self._module_rows(room_data, module)
            for stream_schedule in room.stream_schedules.all():
                yield from self._stream_schedule_rows(room_data, stream_schedule)

    def _rooms(self):
        module_filter = reduce(
            or_,
            (
                Q(module_config__contains=[{"type": module_type}])
                for module_type in BROADCAST_MODULE_TYPES
            ),
        )
        return (
            self.event.rooms.filter(deleted=False)
            .filter(module_filter | Q(stream_schedules__isnull=False))
            .prefetch_related("stream_schedules")
            .distinct()
            .order_by("position", "id")
        )

    def _room_data(self, room):
        return {
            "room_id": room.id,
            "room_name": str(room.name),
            "room_type": self._inferred_room_type(room.module_config),
        }

    def _module_rows(self, room_data, module):
        config = module.get("config") or {}
        module_data = {
            "row_type": "default_stream",
            "module_type": module.get("type", ""),
            "playback_mode": config.get("playback_mode") or "always_on",
            "hls_url": config.get("hls_url", ""),
            "iframe_url": config.get("url", ""),
            "youtube_id": config.get("ytid", ""),
            "subtitles_url": config.get("subtitle_url", ""),
            "stream_offline_image": config.get("streamOfflineImage", ""),
            "mux_env_key": config.get("mux_env_key", ""),
            **{label: bool(config.get(key)) for label, key in YOUTUBE_BOOLEAN_OPTIONS},
        }
        yield self._row(room_data, module_data)

        for alternative in config.get("alternatives") or []:
            yield self._row(
                room_data,
                module_data,
                row_type="hls_alternative",
                alternative_label=alternative.get("label", ""),
                alternative_hls_url=alternative.get("hls_url", ""),
            )

        for language_url in config.get("languageUrls") or []:
            yield self._row(
                room_data,
                module_data,
                row_type="youtube_language_stream",
                language=language_url.get("language", ""),
                language_youtube_id=language_url.get("youtube_id", ""),
                language_url=language_url.get("url", ""),
                language_use_video=bool(language_url.get("use_video")),
            )

    def _stream_schedule_rows(self, room_data, stream_schedule):
        config = stream_schedule.config or {}
        schedule_data = {
            "row_type": "stream_schedule",
            "stream_schedule_id": stream_schedule.id,
            "stream_schedule_title": stream_schedule.title,
            "stream_schedule_url": stream_schedule.url,
            "stream_schedule_start_time": stream_schedule.start_time,
            "stream_schedule_end_time": stream_schedule.end_time,
            "stream_schedule_type": stream_schedule.stream_type,
            "stream_schedule_language": _value(config, "language"),
            "stream_schedule_use_video": bool(_value(config, "use_video", "useVideo")),
        }
        yield self._row(room_data, schedule_data)
        for language_url in config.get("languageUrls") or []:
            yield self._row(
                room_data,
                schedule_data,
                row_type="stream_schedule_language",
                language=language_url.get("language", ""),
                language_youtube_id=language_url.get("youtube_id", ""),
                language_url=language_url.get("url", ""),
                language_use_video=bool(language_url.get("use_video")),
            )

    def _row(self, *sources, **overrides):
        data = {}
        for source in sources:
            data.update(source)
        data.update(overrides)
        return [_cell(data.get(header, "")) for header in self.headers]

    def _inferred_room_type(self, module_config):
        module_types = {module.get("type") for module in module_config or []}
        if module_types & BROADCAST_MODULE_TYPES:
            return "stage"
        if "call.bigbluebutton" in module_types:
            return "bigbluebutton"
        if "call.janus" in module_types:
            return "janus"
        if "call.zoom" in module_types:
            return "zoom"
        if "chat.native" in module_types:
            return "chat"
        if "poster.native" in module_types:
            return "poster"
        if "page.landing" in module_types:
            return "landing_page"
        return ""
