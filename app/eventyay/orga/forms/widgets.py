from django.forms import CheckboxSelectMultiple, RadioSelect


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
        # Single combined, alphabetically sorted list (case-insensitive)
        return sorted(self.choices, key=lambda c: str(c[1]).lower())

    def optgroups(self, name, value, attrs=None):
        self.choices = self._sorted_choices()
        return super().optgroups(name, value, attrs)
