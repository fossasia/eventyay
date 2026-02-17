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
        from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
        from django.utils.translation import get_language
        from django.utils.html import format_html

        # Get the set of valid codes from the original choices
        valid_codes = set(str(c[0]) for c in self.choices)
        
        # Get structured locales (sorted by current locale)
        structured = get_sorted_grouped_locales(get_language())
        
        new_choices = []
        for item in structured:
            code = item['code']
            if code in valid_codes:
                new_choices.append((code, item['styled_name'])) # Styled name: "German (Deutsch)"
            
            # Add variants if they exist and are valid options
            for variant in item.get('variants', []):
                v_code = variant['code']
                if v_code in valid_codes:
                    # Indent variants
                    # We use a special char or HTML entity for indentation
                    label = format_html("&nbsp;&nbsp;&nbsp;&nbsp;↳ {}", variant['name'])
                    new_choices.append((v_code, label))

        # Replace self.choices with our sorted, flattened, and formatted list
        # Note: We temporarily replace it for the generation of optgroups
        original_choices = self.choices
        self.choices = new_choices
        try:
             return super().optgroups(name, value, attrs)
        finally:
             self.choices = original_choices
