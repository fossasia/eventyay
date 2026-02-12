from urllib.request import urlopen

import lxml.html
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.crypto import get_random_string
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

    mimes = {
        'image/gif': 'gif',
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
    }

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Page.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                _('You already have a page on that URL.'),
                code='duplicate_slug',
            )
        return slug

    def clean_text(self):
        text = self.cleaned_data['text']
        data = getattr(text, 'data', None)
        if not isinstance(data, dict):
            return text

        cleaned_data = {}
        for locale, html in data.items():
            if html is None:
                continue
            if isinstance(html, str) and not html.strip():
                continue
            cleaned_data[locale] = process_data_images(html, self.mimes)

        text.data = cleaned_data
        return text

    def save(self, commit=True):
        text = self.cleaned_data.get('text')
        data = getattr(text, 'data', None)
        if not isinstance(data, dict):
            return super().save(commit)

        merged_data = {}
        existing_text = getattr(self.instance, 'text', None)
        existing_data = getattr(existing_text, 'data', None)
        if isinstance(existing_data, dict):
            merged_data.update(existing_data)

        for locale, html in data.items():
            if html is None:
                continue   
            if isinstance(html, str) and not html.strip():
                merged_data.pop(locale, None)
            else:
                merged_data[locale] = html

        text.data = merged_data
        self.cleaned_data['text'] = text
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
