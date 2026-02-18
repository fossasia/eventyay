from django.conf import settings
from django.forms import CheckboxSelectMultiple, RadioSelect
from django.utils import translation


class HeaderSelect(RadioSelect):
    option_template_name = 'orga/widgets/header_option.html'


class MultipleLanguagesWidget(CheckboxSelectMultiple):
    template_name = 'django/forms/widgets/checkbox_select.html'
    option_template_name = 'django/forms/widgets/checkbox_option.html'

    def __init__(self, *args, **kwargs):
        kwargs['attrs'] = kwargs.get('attrs', {})
        kwargs['attrs']['class'] = kwargs['attrs'].get('class', '') + ' multi-language-select'
        kwargs['attrs']['help_left'] = True
        super().__init__(*args, **kwargs)

    def _sorted_choices(self):
        # Sort by English language names, while rendering native labels.
        choices = list(self.choices)
        with translation.override('en'):
            english_names = {code: str(name) for code, name in settings.LANGUAGES}
        return sorted(
            choices,
            key=lambda c: (str(english_names.get(c[0], c[1])).casefold(), str(c[0])),
        )

    def optgroups(self, name, value, attrs=None):
        self.choices = self._sorted_choices()
        return super().optgroups(name, value, attrs)
