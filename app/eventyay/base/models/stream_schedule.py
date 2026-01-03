from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class StreamSchedule(models.Model):
    """A time-based stream schedule for a room."""

    room = models.ForeignKey(
        to="Room",
        related_name="stream_schedules",
        on_delete=models.CASCADE,
        verbose_name=_("Room"),
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Title"),
        help_text=_(
            'Optional label for this stream (e.g., "Day 1 Stream", "Keynotes")'
        ),
    )
    url = models.URLField(
        verbose_name=_("Stream URL"),
        help_text=_("URL of the stream (YouTube, Vimeo, HLS, or other live link)"),
    )
    start_time = models.DateTimeField(
        verbose_name=_("Start Time"),
        help_text=_("When this stream becomes active (UTC)"),
    )
    end_time = models.DateTimeField(
        verbose_name=_("End Time"),
        help_text=_("When this stream stops being active (UTC)"),
    )
    stream_type = models.CharField(
        max_length=50,
        default="youtube",
        choices=[
            ("youtube", "YouTube"),
            ("vimeo", "Vimeo"),
            ("hls", "HLS"),
            ("iframe", "Iframe"),
            ("native", "Native"),
        ],
        verbose_name=_("Stream Type"),
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Additional Configuration"),
        help_text=_(
            "Extra configuration for the stream (e.g., YouTube video ID, language settings)"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_time",)
        verbose_name = _("Stream Schedule")
        verbose_name_plural = _("Stream Schedules")
        indexes = [
            models.Index(fields=["room", "start_time", "end_time"]),
        ]

    def __str__(self):
        if self.title:
            return f"{self.room.name} - {self.title}"
        return f"{self.room.name} - {self.start_time}"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": _("End time must be after start time.")})

        overlapping = StreamSchedule.objects.filter(
            room=self.room, start_time__lt=self.end_time, end_time__gt=self.start_time
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                _(
                    "This stream schedule overlaps with an existing schedule for this room. "
                    "Please ensure stream schedules do not overlap."
                )
            )

        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def is_active(self, at_time=None):
        from django.utils.timezone import now

        at_time = at_time or now()
        return self.start_time <= at_time < self.end_time
