from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.import_utils import build_header_map, match_header
from eventyay.base.orderimport import get_all_columns


class ProcessForm(forms.Form):
    orders = forms.ChoiceField(
        label=_('Import mode'),
        choices=(
            ('many', _('Create a separate order for each line')),
            ('one', _('Create one order with one position per line')),
        ),
    )
    status = forms.ChoiceField(
        label=_('Order status'),
        choices=(
            ('paid', _('Create orders as fully paid')),
            ('pending', _('Create orders as pending and still require payment')),
        ),
    )
    testmode = forms.BooleanField(label=_('Create orders as test mode orders'), required=False)
    create_missing_products = forms.BooleanField(
        label=_('Automatically create missing products'),
        help_text=_(
            'If a product referenced in the CSV does not exist, it will be created automatically. '
            'Existing products continue to be matched by name or ID.'
        ),
        required=False,
    )

    # Names of the non-mapping fields rendered separately in the "Import settings" panel.
    _SETTINGS_FIELDS = frozenset({'orders', 'status', 'testmode', 'create_missing_products'})

    def __init__(self, *args, **kwargs):
        headers = kwargs.pop('headers')
        initial = kwargs.pop('initial', {}) or {}
        self.event = kwargs.pop('event')
        initial['testmode'] = self.event.testmode
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

        header_choices = [('csv:{}'.format(h), _('CSV column: "{name}"').format(name=h)) for h in headers]
        # Build the normalised header map once; reused for every column below.
        header_map = build_header_map(headers)

        for c in get_all_columns(self.event):
            choices = []
            if c.default_value:
                choices.append((c.default_value, c.default_label))
            choices += header_choices
            for k, v in c.static_choices():
                choices.append(('static:{}'.format(k), v))

            all_valid_values = {v for v, _ in choices}

            field = forms.ChoiceField(
                label=str(c.verbose_name),
                choices=choices,
                widget=forms.Select(attrs={'data-static': 'true'}),
            )

            saved = initial.get(c.identifier)
            # Use `is not None` rather than truthiness so that a saved value of
            # '0' or any other falsy-but-valid string is honoured.
            if saved is not None and saved in all_valid_values:
                field.initial = saved
            else:
                # No usable saved mapping: auto-match from CSV headers using the
                # pre-built map, then fall back to the column's built-in default.
                matched = match_header(header_map, getattr(c, 'suggestions', []))
                if matched:
                    field.initial = 'csv:{}'.format(matched)
                elif c.initial is not None and c.initial in all_valid_values:
                    field.initial = c.initial

            self.fields[c.identifier] = field

    @property
    def mapping_fields(self):
        """Yield only the column-mapping fields (excludes the import-settings fields)."""
        for name, field in self.fields.items():
            if name not in self._SETTINGS_FIELDS:
                yield self[name]

