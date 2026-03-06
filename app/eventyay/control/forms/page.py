import base64
import binascii
import logging

import lxml.html
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from lxml import etree

from eventyay.base.forms import I18nMarkdownTextarea
from eventyay.base.models.page import Page

logger = logging.getLogger(__name__)

# Keep inline image payloads reasonably bounded to avoid expensive decoding/storage.
MAX_INLINE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_INLINE_IMAGE_BASE64_LENGTH = ((MAX_INLINE_IMAGE_BYTES + 2) // 3) * 4


class PageSettingsForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = (
            'title',
            'slug',
            'link_on_website_start_page',
            'link_in_header',
            'link_in_footer',
            'confirmation_required',
            'text',
        )
        widgets = {
            'text': I18nMarkdownTextarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['link_on_website_start_page'].widget = forms.HiddenInput()
        # Allow backend fallback generation from title when JS slug generation is unavailable.
        self.fields['slug'].required = False
        # Keep server-side form submission usable even if the rich-text editor JS fails to load.
        self.fields['text'].required = False
        if hasattr(self.fields['text'], 'one_required'):
            self.fields['text'].one_required = False

    mimes = {
        'image/gif': 'gif',
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
    }

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()

        if not slug:
            title = self.cleaned_data.get('title')
            title_values = []
            if hasattr(title, 'data') and isinstance(title.data, dict):
                title_values = [v for v in title.data.values() if v]
            elif title:
                title_values = [str(title)]

            if title_values:
                slug = slugify(title_values[0])[:150]

        if not slug:
            raise forms.ValidationError(
                _('This field is required.'),
                code='required',
            )

        slug_conflict = Page.objects.filter(slug__iexact=slug)
        if self.instance and self.instance.pk:
            slug_conflict = slug_conflict.exclude(pk=self.instance.pk)
        if slug_conflict.exists():
            raise forms.ValidationError(
                _('You already have a page on that URL.'),
                code='duplicate_slug',
            )
        return slug

    def clean_text(self):
        t = self.cleaned_data.get('text')
        if not t or not hasattr(t, 'data'):
            return t
        for locale, html in t.data.items():
            t.data[locale] = process_data_images(html or '', self.mimes)
        return t

    def save(self, commit=True):
        return super().save(commit)


def decode_data_image_url(data_url: str, allowed_mimes):
    header, separator, payload = str(data_url).partition(',')
    if separator != ',':
        raise ValueError('Malformed data URL: missing payload separator')

    metadata = header[5:]  # strip leading "data:"
    parts = [part.strip() for part in metadata.split(';') if part.strip()]
    if not parts:
        raise ValueError('Malformed data URL: missing mime type')

    mime = parts[0].lower()
    if mime not in allowed_mimes:
        return None

    if 'base64' not in {part.lower() for part in parts[1:]}:
        raise ValueError('Malformed data URL: only base64 payloads are supported')

    compact_payload = ''.join(payload.split())
    if len(compact_payload) > MAX_INLINE_IMAGE_BASE64_LENGTH:
        raise ValueError('Inline image payload exceeds maximum allowed size')

    try:
        decoded = base64.b64decode(compact_payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('Malformed data URL: invalid base64 payload') from exc

    if len(decoded) > MAX_INLINE_IMAGE_BYTES:
        raise ValueError('Inline image exceeds maximum allowed size')

    return mime, decoded


def process_data_images(content, allowed_mimes):
    if not content:
        return ''

    try:
        fragments = lxml.html.fragments_fromstring(content)
    except (etree.ParserError, TypeError, ValueError):
        return content

    processed_fragments = []
    for fragment in fragments:
        if isinstance(fragment, str):
            processed_fragments.append(fragment)
            continue

        if not hasattr(fragment, 'xpath'):
            processed_fragments.append(str(fragment))
            continue

        for image in fragment.xpath('.//img[@src]'):
            original_image_src = image.attrib['src']
            if original_image_src.startswith('data:'):
                try:
                    decoded_payload = decode_data_image_url(original_image_src, allowed_mimes)
                except ValueError as exc:
                    logger.warning('Dropping invalid inline page image: %s', exc)
                    image.attrib.pop('src', None)
                    continue

                if not decoded_payload:
                    continue

                ftype, binary_content = decoded_payload
                try:
                    cfile = ContentFile(binary_content)
                    nonce = get_random_string(length=32)
                    name = f'pub/pages/img/{nonce}.{allowed_mimes[ftype]}'
                    stored_name = default_storage.save(name, cfile)
                    stored_url = default_storage.url(stored_name)
                    image.attrib['src'] = stored_url
                except Exception:
                    logger.exception('Failed to persist inline page image')
                    image.attrib.pop('src', None)
        processed_fragments.append(lxml.html.tostring(fragment, encoding='unicode'))

    return ''.join(processed_fragments)
