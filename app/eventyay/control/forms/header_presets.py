import io
import os
from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

from eventyay.base.forms import I18nModelForm
from eventyay.base.header_presets import invalidate_preset_cache
from eventyay.base.models.event_header_preset import EventHeaderPreset, EventHeaderPresetCategory


def optimize_header_preset_images(uploaded_file):
    """
    Given an uploaded image, process and return (full_file, thumb_file).
    Full image: 1920x640 JPEG (quality 85)
    Thumbnail: 400x133 JPEG (quality 80)
    """
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')

    # 1. Full image (1920x640)
    full_target_size = (1920, 640)
    full_img = ImageOps.fit(img, full_target_size, method=Image.Resampling.LANCZOS)
    if full_img.mode == 'RGBA':
        background = Image.new('RGB', full_img.size, (255, 255, 255))
        background.paste(full_img, mask=full_img.split()[3])
        full_img = background

    full_buffer = io.BytesIO()
    full_img.save(full_buffer, format='JPEG', quality=85, optimize=True)
    full_file = ContentFile(full_buffer.getvalue())

    # 2. Thumbnail (400x133)
    thumb_target_size = (400, 133)
    thumb_img = ImageOps.fit(full_img, thumb_target_size, method=Image.Resampling.LANCZOS)
    thumb_buffer = io.BytesIO()
    thumb_img.save(thumb_buffer, format='JPEG', quality=80, optimize=True)
    thumb_file = ContentFile(thumb_buffer.getvalue())

    base_name = os.path.splitext(uploaded_file.name)[0]
    safe_name = slugify(base_name) or 'preset'
    full_file.name = f'{safe_name}.jpg'
    thumb_file.name = f'{safe_name}_thumb.jpg'

    return full_file, thumb_file


class EventHeaderPresetForm(I18nModelForm):
    image = forms.ImageField(
        label=_('Full-size image (1920 × 640 px)'),
        required=True,
        help_text=_('Upload a banner image. It will be automatically optimized to 1920 × 640 px with a thumbnail generated.'),
    )

    class Meta:
        model = EventHeaderPreset
        fields = ['name', 'category', 'image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.image:
            self.fields['image'].required = False

    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and isinstance(image, UploadedFile):
            if image.size > self.MAX_IMAGE_SIZE:
                raise forms.ValidationError(_('The uploaded image exceeds the maximum allowed size of 10 MB.'))
            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                raise forms.ValidationError(_('The uploaded file is not a valid or supported image format.'))
        return image

    def save(self, commit=True):
        old_image = None
        old_thumbnail = None
        if self.instance and self.instance.pk:
            current = EventHeaderPreset.objects.filter(pk=self.instance.pk).values('image', 'thumbnail').first()
            if current:
                old_image = current.get('image')
                old_thumbnail = current.get('thumbnail')

        instance = super().save(commit=False)
        uploaded_image = self.cleaned_data.get('image')

        has_new_upload = bool(uploaded_image and isinstance(uploaded_image, UploadedFile))
        if has_new_upload:
            full_file, thumb_file = optimize_header_preset_images(uploaded_image)
            instance.image.save(full_file.name, full_file, save=False)
            instance.thumbnail.save(thumb_file.name, thumb_file, save=False)

        if commit:
            instance.save()
            if has_new_upload and (old_image or old_thumbnail):
                def _cleanup_old_files():
                    from contextlib import suppress
                    from django.core.files.storage import default_storage
                    if old_image and old_image != instance.image.name:
                        with suppress(OSError):
                            default_storage.delete(old_image)
                    if old_thumbnail and old_thumbnail != instance.thumbnail.name:
                        with suppress(OSError):
                            default_storage.delete(old_thumbnail)

                from django.db import transaction
                transaction.on_commit(_cleanup_old_files)

            invalidate_preset_cache()
        return instance


class EventHeaderPresetCategoryForm(I18nModelForm):
    class Meta:
        model = EventHeaderPresetCategory
        fields = ['name']

    def save(self, commit=True):
        instance = super().save(commit=commit)
        invalidate_preset_cache()
        return instance
