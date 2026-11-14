import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.privacy import ThirdPartyService


def cookie_pattern_problem(pattern):
    """Why a browser's RegExp would refuse ``pattern``, or ``None`` if it compiles."""
    try:
        re.compile(pattern)
    except re.error as e:
        return e.msg
    # Escapes and character classes can hold a literal "(?" or "*+", so drop them first.
    syntax = re.sub(r'\[\^?\]?[^\]]*\]', '', re.sub(r'\\.', '', pattern))
    if re.search(r'\(\?(?![:=!]|<[=!])', syntax):
        return _('browsers only support the (?: (?= (?! (?<= and (?<! groups')
    if re.search(r'(?:[*+?]|\{\d*,?\d*\})\+', syntax):
        return _('browsers do not support possessive quantifiers')
    return None


class ThirdPartyServiceForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyService
        fields = [
            'title',
            'name',
            'provider',
            'purpose',
            'category',
            'enabled',
            'privacy_policy_url',
            'cookie_names',
            'data_processed',
            'region',
            'dpa_status',
        ]
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'cookie_names': forms.Textarea(attrs={'rows': 3}),
            'data_processed': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model allows a blank category, but a service without one is left
        # out of the consent banner entirely, so visitors could never allow it.
        # Required unless the stored service has none yet, so an older service
        # without a category can still be opened and classified, while a
        # classified one can never be put back into that state.
        self.fields['category'].required = not self.instance.pk or bool(self.instance.category)
        self.fields['category'].choices = [('', _('Choose a consent category'))] + [
            choice for choice in self.fields['category'].choices if choice[0]
        ]
        if self.instance.pk:
            # Blocked scripts are matched on this identifier, so renaming a live
            # service would silently stop blocking them.
            self.fields['name'].disabled = True
            self.fields['name'].help_text = _('The identifier cannot be changed once the service exists.')

    def clean_cookie_names(self):
        # A cookie name cannot contain a comma or whitespace, so "_ga, _gid" is
        # two names. A line starting with ^ is a regular expression, kept whole.
        names = []
        for line in self.cleaned_data['cookie_names'].splitlines():
            entry = line.strip()
            if entry.startswith('^'):
                names.append(entry)
            else:
                names.extend(name for name in re.split(r'[\s,]+', entry) if name)

        # Klaro compiles these in the visitor's browser without catching errors,
        # so one bad pattern stops it from clearing cookies at all.
        errors = []
        for name in names:
            problem = cookie_pattern_problem(name) if name.startswith('^') else None
            if problem:
                errors.append(
                    ValidationError(
                        _('"%(pattern)s" is not a valid regular expression: %(problem)s.'),
                        params={'pattern': name, 'problem': problem},
                    )
                )
        if errors:
            raise ValidationError(errors)
        return '\n'.join(names)
