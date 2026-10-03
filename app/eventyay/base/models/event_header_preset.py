from contextlib import suppress
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField

from eventyay.base.models.base import LoggedModel


class EventHeaderPresetCategory(LoggedModel):
    name = I18nCharField(
        max_length=100,
        verbose_name=_('Category name'),
    )

    class Meta:
        verbose_name = _('Header preset category')
        verbose_name_plural = _('Header preset categories')
        ordering = ['id']

    def __str__(self):
        return str(self.name)


class EventHeaderPreset(LoggedModel):
    name = I18nCharField(
        max_length=150,
        verbose_name=_('Preset name'),
    )
    category = models.ForeignKey(
        EventHeaderPresetCategory,
        on_delete=models.CASCADE,
        related_name='presets',
        verbose_name=_('Category'),
    )
    image = models.FileField(
        upload_to='header_presets/',
        max_length=255,
        verbose_name=_('Full-size image (1920 × 640 px)'),
    )
    thumbnail = models.FileField(
        upload_to='header_presets/thumbs/',
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Thumbnail image (400 × 133 px)'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('If disabled, this preset will not appear in the event creation gallery.'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at'),
    )

    class Meta:
        verbose_name = _('Event header preset')
        verbose_name_plural = _('Event header presets')
        ordering = ['id']

    def __str__(self):
        return str(self.name)


@receiver(post_delete, sender=EventHeaderPreset)
def cleanup_event_header_preset_files(sender, instance, **kwargs):
    """Clean up image and thumbnail files from storage after deletion (including cascade delete)."""
    image_name = instance.image.name if instance.image else None
    thumb_name = instance.thumbnail.name if instance.thumbnail else None

    def _delete():
        with suppress(OSError):
            if image_name:
                default_storage.delete(image_name)
        with suppress(OSError):
            if thumb_name:
                default_storage.delete(thumb_name)
        from eventyay.base.header_presets import invalidate_preset_cache
        invalidate_preset_cache()

    transaction.on_commit(_delete)


@receiver(post_delete, sender=EventHeaderPresetCategory)
def cleanup_event_header_preset_category(sender, instance, **kwargs):
    """Invalidate cache when a preset category is deleted."""
    from eventyay.base.header_presets import invalidate_preset_cache
    transaction.on_commit(invalidate_preset_cache)


@receiver(post_save, sender=EventHeaderPreset)
@receiver(post_save, sender=EventHeaderPresetCategory)
def invalidate_cache_on_save(sender, instance, **kwargs):
    """Invalidate cache when a preset or category is created or updated."""
    from eventyay.base.header_presets import invalidate_preset_cache
    transaction.on_commit(invalidate_preset_cache)
