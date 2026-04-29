from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.orderimport import _match_header, get_all_columns


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

    def __init__(self, *args, **kwargs):
        headers = kwargs.pop('headers')
        initial = kwargs.pop('initial', {}) or {}
        self.event = kwargs.pop('event')
        initial['testmode'] = self.event.testmode
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

        header_choices = [('csv:{}'.format(h), _('CSV column: "{name}"').format(name=h)) for h in headers]
        valid_csv_values = {v for v, _ in header_choices}

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
            if saved and saved in all_valid_values:
                # Saved mapping is valid for this file — honour it.
                field.initial = saved
            else:
                # No usable saved mapping: auto-match from CSV headers, then fall back to
                # the column's built-in default (e.g. a static country from guess_country).
                suggestions = getattr(c, 'suggestions', [])
                matched = _match_header(headers, suggestions) if suggestions else None
                if matched:
                    field.initial = 'csv:{}'.format(matched)
                elif c.initial is not None and c.initial in all_valid_values:
                    field.initial = c.initial

            self.fields[c.identifier] = field

