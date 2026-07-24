from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import SpeakerSocialLink
from eventyay.common.social_links import (
    SOCIAL_LINK_CHOICES,
    build_social_link_url,
    get_social_link_value,
)


class SpeakerSocialLinkForm(forms.Form):
    network = forms.ChoiceField(
        choices=(('', _('Choose social platform')),) + SOCIAL_LINK_CHOICES,
        required=False,
        label=_('Social platform'),
    )
    path = forms.CharField(
        required=False,
        label=_('Profile or path'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['network'].widget.attrs.update({'class': 'form-control'})
        self.fields['path'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': _('Profile, handle, or full URL'),
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        network = cleaned_data.get('network', '')
        path = (cleaned_data.get('path') or '').strip()

        if cleaned_data.get('DELETE'):
            return cleaned_data

        if not network and not path:
            if self.has_changed():
                self.add_error(
                    'path',
                    _('Please enter a profile, handle, or URL or remove this row.'),
                )
            cleaned_data['url'] = ''
            return cleaned_data

        if not network:
            self.add_error('network', _('Please choose a social platform.'))
            return cleaned_data

        if not path:
            self.add_error('path', _('Please enter a profile, handle, or URL.'))
            return cleaned_data

        try:
            cleaned_data['url'] = build_social_link_url(network, path)
        except ValidationError as exc:
            self.add_error('path', exc)
        return cleaned_data


SpeakerSocialLinkFormSet = formset_factory(
    SpeakerSocialLinkForm,
    can_delete=True,
    extra=0,
)


def social_links_formset_initial(profile) -> list[dict]:
    if not profile or not getattr(profile, 'pk', None):
        return []
    return [
        {
            'network': link.network,
            'path': get_social_link_value(link.url, link.network),
        }
        for link in profile.social_links.all()
    ]


def build_speaker_social_links_formset(profile=None, data=None, initial=None, prefix='social_links'):
    kwargs = {'prefix': prefix}
    if data is not None:
        kwargs['data'] = data
    else:
        kwargs['initial'] = initial if initial is not None else social_links_formset_initial(profile)
    return SpeakerSocialLinkFormSet(**kwargs)


def save_speaker_social_links(profile, formset) -> None:
    links = []
    for form in formset:
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue
        url = cleaned.get('url') or ''
        network = cleaned.get('network') or ''
        if not url or not network:
            continue
        links.append(SpeakerSocialLink(profile=profile, network=network, url=url))

    profile.social_links.all().delete()
    if links:
        SpeakerSocialLink.objects.bulk_create(links)


def cleaned_social_links_from_formset(formset) -> list[dict]:
    links = []
    for form in formset:
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue
        url = cleaned.get('url') or ''
        network = cleaned.get('network') or ''
        if url and network:
            links.append({'network': network, 'url': url, 'path': cleaned.get('path') or ''})
    return links


def formset_has_social_links(formset) -> bool:
    return bool(cleaned_social_links_from_formset(formset))


__all__ = [
    'SpeakerSocialLinkForm',
    'SpeakerSocialLinkFormSet',
    'build_speaker_social_links_formset',
    'cleaned_social_links_from_formset',
    'formset_has_social_links',
    'save_speaker_social_links',
    'social_links_formset_initial',
]
