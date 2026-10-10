from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString

from eventyay.common.language import language
from eventyay.common.text.phrases import phrases


TARGET_TO_STEP = {
    'session': 'info',
    'speaker': 'profile',
}

STEP_TO_TARGET = {
    'info': 'session',
    'profile': 'speaker',
}

BUILTIN_FIELD_DEFAULTS = {
    'session': {
        'title': {
            'label': _('Proposal title'),
            'help_text': '',
        },
        'submission_type': {
            'label': _('Session type'),
            'help_text': '',
        },
        'track': {
            'label': _('Track'),
            'help_text': '',
        },
        'content_locale': {
            'label': phrases.base.language,
            'help_text': '',
        },
        'abstract': {
            'label': _('Abstract'),
            'help_text': phrases.base.use_markdown,
        },
        'description': {
            'label': _('Description'),
            'help_text': phrases.base.use_markdown,
        },
        'notes': {
            'label': _('Notes'),
            'help_text': _('These notes are meant for the organiser and won’t be made public.'),
        },
        'slot_count': {
            'label': _('Slot Count'),
            'help_text': _('How many times this session will take place.'),
        },
        'do_not_record': {
            'label': _('Don’t record this session.'),
            'help_text': '',
        },
        'image': {
            'label': _('Session image'),
            'help_text': _('Use this if you want an illustration to go with your proposal.'),
        },
        'slides': {
            'label': _('Slides'),
            'help_text': _('Upload PDF files. Only PDF is supported right now.'),
        },
        'duration': {
            'label': _('Duration'),
            'help_text': _('The duration in minutes.'),
        },
    },
    'speaker': {
        'fullname': {
            'label': _('Full name'),
            'help_text': '',
        },
        'biography': {
            'label': _('Biography'),
            'help_text': phrases.base.use_markdown,
        },
        'job_title': {
            'label': _('Job title/role'),
            'help_text': _('What is your official job title?'),
        },
        'organization': {
            'label': _('Organization'),
            'help_text': _('What organization or company do you represent?'),
        },
        'avatar': {
            'label': _('Profile picture'),
            'help_text': _(
                'We recommend uploading an image at least 400px wide. '
                'A square image works best, as we display it in a circle in several places.'
            ),
        },
        'avatar_source': {
            'label': _('Profile Picture Source'),
            'help_text': _('Please enter the name of the author or source of image and a link if applicable.'),
        },
        'avatar_license': {
            'label': _('Profile Picture License'),
            'help_text': _('Please enter the name of the license of the photo and link to it if applicable.'),
        },
        'availabilities': {
            'label': _('Availability'),
            'help_text': '',
        },
        'additional_speaker': {
            'label': _('Additional Speaker'),
            'help_text': _(
                'If you have a co-speaker, please add their email address here, and we will invite them '
                'to create an account. If you have more than one co-speaker, you can add more speakers '
                'after finishing the proposal process.'
            ),
        },
        'social_links': {
            'label': _('Social Links'),
            'help_text': '',
        },
    },
}


class CfPLazyI18nString(LazyI18nString):
    """LazyI18nString that uses a built-in default for missing locales.

    If a locale is missing from data (or is None), it resolves to the built-in
    default for that locale instead of falling back to an unrelated locale.
    """

    def __init__(self, data, default=None):
        if isinstance(data, LazyI18nString):
            if default is None and hasattr(data, 'default'):
                default = data.default
            data = data.data
        super().__init__(data)
        self.default = default

    def localize(self, lng: str) -> str:
        if self.data is None:
            if self.default is not None:
                with language(lng):
                    return str(self.default) if self.default else ''
            return ''
        if isinstance(self.data, dict):
            firstpart = lng.split('-')[0]
            similar = [
                loc for loc in self.data.keys()
                if (loc.startswith(firstpart + '-') or firstpart == loc) and loc != lng
            ]
            if lng in self.data and self.data[lng] is not None:
                return self.data[lng]
            elif firstpart in self.data and self.data[firstpart] is not None:
                return self.data[firstpart]
            elif similar and any(self.data.get(s) is not None for s in similar):
                for s in similar:
                    if self.data.get(s) is not None:
                        return self.data[s]
            elif self.default is not None:
                with language(lng):
                    return str(self.default) if self.default else ''
        return super().localize(lng)
