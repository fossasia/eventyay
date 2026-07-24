from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay.person.forms import (
    build_speaker_social_links_formset,
    formset_has_social_links,
    save_speaker_social_links,
    social_link_prefixes,
)


class SpeakerSocialLinksMixin:
    """Attach an optional social-links formset when the CfP field is enabled."""

    social_links_session_key = '_social_links'

    def social_links_enabled(self):
        event = getattr(self, 'event', None) or getattr(getattr(self, 'request', None), 'event', None)
        return bool(event and event.cfp.request_social_links)

    def social_links_required(self):
        event = getattr(self, 'event', None) or getattr(getattr(self, 'request', None), 'event', None)
        return bool(event and event.cfp.require_social_links)

    def social_links_should_bind_post(self):
        request = getattr(self, 'request', None)
        return bool(request and request.method == 'POST')

    def get_social_links_profile(self):
        raise NotImplementedError

    def get_social_links_initial(self):
        return None

    @cached_property
    def social_media_formset(self):
        if not self.social_links_enabled():
            return None
        request = getattr(self, 'request', None)
        data = request.POST if self.social_links_should_bind_post() else None
        return build_speaker_social_links_formset(
            profile=self.get_social_links_profile(),
            data=data,
            initial=None if data is not None else self.get_social_links_initial(),
        )

    def social_media_formset_is_valid(self):
        formset = self.social_media_formset
        if formset is None:
            return True
        if not formset.is_valid():
            return False
        if self.social_links_required() and not formset_has_social_links(formset):
            formset.non_form_errors().append(_('Please add at least one social media link.'))
            return False
        return True

    def save_social_media_formset(self, profile=None):
        formset = self.social_media_formset
        if formset is None:
            return
        profile = profile or self.get_social_links_profile()
        save_speaker_social_links(profile, formset)

    def get_social_links_context(self):
        formset = self.social_media_formset
        if formset is None:
            return {
                'social_media_formset': None,
                'social_link_prefixes': {},
                'show_social_links': False,
            }
        return {
            'social_media_formset': formset,
            'social_link_prefixes': social_link_prefixes(),
            'show_social_links': True,
        }
