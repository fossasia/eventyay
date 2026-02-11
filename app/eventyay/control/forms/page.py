from urllib.request import urlopen

import lxml.html
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.page import Page


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
        t = self.cleaned_data.get('text')
        if t and hasattr(t, 'data'):
            for locale, html in t.data.items():
                t.data[locale] = process_data_images(html or '', self.mimes)
        return super().save(commit)


def process_data_images(html, allowed_mimes):
    processed_html = ''
    etrees = lxml.html.fragments_fromstring(html)
    for etree in etrees:
        for image in etree.xpath('//img'):
            original_image_src = image.attrib['src']
            if original_image_src.startswith('data:'):
                ftype = original_image_src.split(';')[0][5:]
                if ftype in allowed_mimes:
                    with urlopen(original_image_src) as response:
                        cfile = ContentFile(response.read())
                        nonce = get_random_string(length=32)
                        name = f'pub/pages/img/{nonce}.{allowed_mimes[ftype]}'
                        stored_name = default_storage.save(name, cfile)
                        stored_url = default_storage.url(stored_name)
                        image.attrib['src'] = stored_url
        processed_html += lxml.html.tostring(etree).decode()
    return processed_html
