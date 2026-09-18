import csv
from collections import namedtuple
from io import StringIO

from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import EmailValidator
from django.db.models import Q
from django.db.models.functions import Upper
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes.forms import SafeModelChoiceField

from eventyay.base.email import get_available_placeholders
from eventyay.base.forms import I18nModelForm, PlaceholderValidator
from eventyay.base.models import Product, Voucher
from eventyay.control.forms import SplitDateTimeField, SplitDateTimePickerWidget
from eventyay.control.forms.widgets import MultipleProductVarQuotaWidget, Select2
from eventyay.control.signals import voucher_form_validation
from eventyay.helpers.models import modelcopy


ALL_PRODUCTS = 'all'


class FakeChoiceField(forms.ChoiceField):
    def valid_value(self, value):
        return True


class FakeMultipleChoiceField(forms.MultipleChoiceField):
    """Accept values that may not be in the preloaded choice list during partial posts."""

    def valid_value(self, value):
        return True

    def to_python(self, value):
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [str(v) for v in value if v not in (None, '')]


def build_productvar_choices(event, extra_products=None):
    """Build product / variation / quota choices for voucher scope selection.

    ``extra_products`` keeps currently selected products visible when editing,
    including legacy add-on selections that new vouchers cannot choose.
    """
    choices = [(ALL_PRODUCTS, _('All products'))]
    extra_pks = {p.pk for p in (extra_products or []) if getattr(p, 'pk', None)}
    products = (
        event.products.filter(
            Q(category__isnull=True) | Q(category__is_addon=False) | Q(pk__in=extra_pks)
        )
        .prefetch_related('variations')
        .order_by('category__position', 'category_id', 'position', 'pk')
    )
    for product in products:
        variations = list(product.variations.all())
        if variations:
            choices.append((str(product.pk), _('{product} – Any variation').format(product=product)))
            for variation in variations:
                choices.append(('%d-%d' % (product.pk, variation.pk), '%s – %s' % (str(product), variation.value)))
        else:
            choices.append((str(product.pk), str(product)))
    for quota in event.quotas.order_by('name', 'pk'):
        choices.append(('q-%d' % quota.pk, _('Any product in quota "{quota}"').format(quota=quota)))
    return choices


class VoucherForm(I18nModelForm):
    productvar = FakeMultipleChoiceField(
        label=_('Product'),
        help_text=_(
            'Select one or more products this voucher applies to. Leave empty or choose "All products" '
            'to allow any product. You can also select a quota to allow any product in that quota.'
        ),
        required=False,
    )

    class Meta:
        model = Voucher
        localized_fields = '__all__'
        fields = [
            'code',
            'valid_until',
            'block_quota',
            'allow_ignore_quota',
            'allow_ignore_approval',
            'value',
            'tag',
            'comment',
            'max_usages',
            'price_mode',
            'subevent',
            'show_hidden_products',
            'budget',
        ]
        field_classes = {
            'valid_until': SplitDateTimeField,
            'subevent': SafeModelChoiceField,
        }
        widgets = {
            'valid_until': SplitDateTimePickerWidget(),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        kwargs.setdefault('initial', {})
        initial = kwargs['initial']
        if instance:
            self.initial_instance_data = modelcopy(instance)
            if 'productvar' not in initial:
                try:
                    if instance.pk and (instance.limit_products.exists() or instance.limit_variations.exists()):
                        initial['productvar'] = [str(p.pk) for p in instance.limit_products.all()] + [
                            '%d-%d' % (v.product_id, v.pk) for v in instance.limit_variations.all()
                        ]
                    elif instance.variation:
                        initial['productvar'] = ['%d-%d' % (instance.product.pk, instance.variation.pk)]
                    elif instance.product:
                        initial['productvar'] = [str(instance.product.pk)]
                    elif instance.quota:
                        initial['productvar'] = ['q-%d' % instance.quota.pk]
                    else:
                        initial['productvar'] = [ALL_PRODUCTS]
                except Product.DoesNotExist:
                    initial['productvar'] = [ALL_PRODUCTS]
        else:
            self.initial_instance_data = None
        super().__init__(*args, **kwargs)
        self._limit_products = []
        self._limit_variations = []

        if instance.event.has_subevents:
            self.fields['subevent'].queryset = instance.event.subevents.all()
            self.fields['subevent'].widget = Select2(
                attrs={
                    'data-model-select2': 'event',
                    'data-select2-url': reverse(
                        'control:event.subevents.select2',
                        kwargs={
                            'event': instance.event.slug,
                            'organizer': instance.event.organizer.slug,
                        },
                    ),
                    'data-placeholder': pgettext_lazy('subevent', 'Date'),
                }
            )
            self.fields['subevent'].widget.choices = self.fields['subevent'].choices
            self.fields['subevent'].required = False
        elif 'subevent':
            del self.fields['subevent']

        extra_products = []
        if instance.pk:
            extra_products.extend(instance.limit_products.all())
            if instance.product_id:
                extra_products.append(instance.product)
        # Include products from initial productvar (e.g. bulk copy with pk=None).
        for token in initial.get('productvar') or []:
            token = str(token)
            if not token or token == ALL_PRODUCTS or token.startswith('q-'):
                continue
            product_id = token.split('-', 1)[0]
            try:
                extra_products.append(instance.event.products.get(pk=product_id))
            except (Product.DoesNotExist, ValueError):
                continue
        choices = build_productvar_choices(instance.event, extra_products=extra_products)
        self.fields['productvar'].choices = choices
        self.fields['productvar'].widget = MultipleProductVarQuotaWidget()
        self.fields['productvar'].required = False
        self.fields['productvar'].hide_optional = True
        self.fields['productvar'].widget.choices = self.fields['productvar'].choices
        if 'valid_until' in self.fields:
            self.fields['valid_until'].hide_optional = True

        if (
            self.instance.event.seating_plan
            or self.instance.event.subevents.filter(seating_plan__isnull=False).exists()
        ):
            self.fields['seat'] = forms.CharField(
                label=_('Specific seat ID'),
                max_length=255,
                required=False,
                widget=forms.TextInput(attrs={'data-seat-guid-field': '1'}),
                initial=self.instance.seat.seat_guid if self.instance.seat else '',
                help_text=str(self.instance.seat) if self.instance.seat else '',
            )

    def _parse_productvar_selection(self, values):
        """Return (quota, product, variation, limit_products, limit_variations)."""
        values = [str(v) for v in (values or []) if v]
        if ALL_PRODUCTS in values:
            if len(values) > 1:
                raise ValidationError(
                    _('"All products" cannot be combined with other product or quota selections.')
                )
            return None, None, None, [], []

        quotas = [v for v in values if v.startswith('q-')]
        products = [v for v in values if not v.startswith('q-')]
        if quotas and products:
            raise ValidationError(_('You cannot select a quota and a specific product at the same time.'))
        if len(quotas) > 1:
            raise ValidationError(_('Please select only one quota.'))
        if quotas:
            quota = self.instance.event.quotas.get(pk=quotas[0][2:])
            return quota, None, None, [], []

        limit_products = []
        limit_variations = []
        seen_products = set()
        seen_variations = set()
        for iv in products:
            if '-' in iv:
                productid, varid = iv.split('-', 1)
                product = self.instance.event.products.get(pk=productid)
                variation = product.variations.get(pk=varid)
                if variation.pk not in seen_variations:
                    limit_variations.append(variation)
                    seen_variations.add(variation.pk)
            else:
                product = self.instance.event.products.get(pk=iv)
                if product.pk not in seen_products:
                    limit_products.append(product)
                    seen_products.add(product.pk)

        # Product-wide "any variation" supersedes specific variation picks for that product.
        product_wide_ids = {p.pk for p in limit_products}
        limit_variations = [v for v in limit_variations if v.product_id not in product_wide_ids]

        # Single selection keeps the legacy FK fields for API / display compatibility
        if len(limit_products) + len(limit_variations) == 1:
            if limit_variations:
                variation = limit_variations[0]
                return None, variation.product, variation, [], []
            return None, limit_products[0], None, [], []

        return None, None, None, limit_products, limit_variations

    def clean(self):
        data = super().clean()

        if not self._errors:
            try:
                quota, product, variation, limit_products, limit_variations = self._parse_productvar_selection(
                    data.get('productvar')
                )
                self.instance.quota = quota
                self.instance.product = product
                self.instance.variation = variation
                self._limit_products = limit_products
                self._limit_variations = limit_variations
            except (ObjectDoesNotExist, ValueError):
                raise ValidationError(_('Invalid product selected.'))

        if 'codes' in data:
            data['codes'] = [a.strip() for a in data.get('codes', '').strip().split('\n') if a]
            cnt = len(data['codes']) * data.get('max_usages', 0)
        else:
            cnt = data.get('max_usages', 0)

        Voucher.clean_product_properties(
            data,
            self.instance.event,
            self.instance.quota,
            self.instance.product,
            self.instance.variation,
            seats_given=data.get('seat') or data.get('seats'),
            block_quota=data.get('block_quota'),
            limit_products=getattr(self, '_limit_products', []),
            limit_variations=getattr(self, '_limit_variations', []),
        )
        if not self.instance.show_hidden_products:
            limited = getattr(self, '_limit_products', []) or getattr(self, '_limit_variations', [])
            all_limits_hidden = bool(limited) and all(
                i.hide_without_voucher for i in getattr(self, '_limit_products', [])
            ) and all(v.product.hide_without_voucher for v in getattr(self, '_limit_variations', []))
            if (
                (self.instance.quota and all(i.hide_without_voucher for i in self.instance.quota.products.all()))
                or (self.instance.product and self.instance.product.hide_without_voucher)
                or all_limits_hidden
            ):
                raise ValidationError(
                    {
                        'show_hidden_products': [
                            _(
                                'The voucher only matches hidden products but you have not selected that it should show '
                                'them.'
                            )
                        ]
                    }
                )
        Voucher.clean_subevent(data, self.instance.event)
        Voucher.clean_max_usages(data, self.instance.redeemed)
        check_quota = Voucher.clean_quota_needs_checking(
            data,
            self.initial_instance_data,
            product_changed=data.get('productvar') != self.initial.get('productvar'),
            creating=not self.instance.pk,
        )
        if check_quota:
            Voucher.clean_quota_check(
                data,
                cnt,
                self.initial_instance_data,
                self.instance.event,
                self.instance.quota,
                self.instance.product,
                self.instance.variation,
                limit_products=getattr(self, '_limit_products', []),
                limit_variations=getattr(self, '_limit_variations', []),
            )
        Voucher.clean_voucher_code(data, self.instance.event, self.instance.pk)
        Voucher.clean_value_and_budget(data)
        if 'seat' in self.fields and data.get('seat'):
            limit_products = getattr(self, '_limit_products', [])
            limit_variations = getattr(self, '_limit_variations', [])
            if limit_products or limit_variations:
                raise ValidationError(
                    _('You cannot select a specific seat together with multiple products.')
                )
            self.instance.seat = Voucher.clean_seat_id(
                data,
                self.instance.product,
                self.instance.quota,
                self.instance.event,
                self.instance.pk,
            )
            self.instance.product = self.instance.seat.product

        voucher_form_validation.send(sender=self.instance.event, form=self, data=data)

        return data

    def _post_clean(self):
        super()._post_clean()
        for field, error_list in list(self._errors.items()):
            seen = set()
            unique_errors = []
            for err in error_list:
                msg = str(err)
                if msg not in seen:
                    seen.add(msg)
                    unique_errors.append(err)
            self._errors[field] = self.error_class(unique_errors, renderer=self.renderer)

    def _apply_product_limits(self, instance):
        instance.limit_products.set(getattr(self, '_limit_products', []))
        instance.limit_variations.set(getattr(self, '_limit_variations', []))

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._apply_product_limits(instance)
        else:
            old_save_m2m = self.save_m2m

            def save_m2m():
                old_save_m2m()
                self._apply_product_limits(instance)

            self.save_m2m = save_m2m
        return instance


class VoucherBulkForm(VoucherForm):
    codes = forms.CharField(
        widget=forms.Textarea,
        label=_('Codes'),
        help_text=_('Add one voucher code per line. We suggest that you copy this list and save it into a file.'),
        required=True,
    )
    use_tag_as_prefix = forms.BooleanField(
        label=_('Use tag as voucher code prefix'),
        help_text=_('Prefix every voucher code with the tag.'),
        required=False,
    )
    send = forms.BooleanField(label=_('Send vouchers via email'), required=False)
    send_subject = forms.CharField(
        label=_('Subject'),
        widget=forms.TextInput(attrs={'data-display-dependency': '#id_send'}),
        required=False,
        initial=_('Your voucher for {event}'),
    )
    send_message = forms.CharField(
        label=_('Message'),
        widget=forms.Textarea(attrs={'data-display-dependency': '#id_send'}),
        required=False,
        initial=_(
            'Hello,\n\n'
            "with this email, we're sending you one or more vouchers for {event}:\n\n{voucher_list}\n\n"
            'You can redeem them here in our ticket shop:\n\n{url}\n\nBest regards,\n\n'
            'Your {event} team'
        ),
    )
    send_recipients = forms.CharField(
        label=_('Recipients'),
        widget=forms.Textarea(
            attrs={
                'data-display-dependency': '#id_send',
                'placeholder': 'email,number,name,tag\njohn@example.org,3,John,example\n\n-- {} --\n\njohn@example.org\njane@example.net'.format(
                    _('or')
                ),
            }
        ),
        required=False,
        help_text=_(
            'You can either supply a list of email addresses with one email address per line, or a CSV file with a title column '
            'and one or more of the columns "email", "number", "name", or "tag".'
        ),
    )
    Recipient = namedtuple('Recipient', 'email number name tag')

    def _set_field_placeholders(self, fn, base_parameters):
        phs = ['{%s}' % p for p in sorted(get_available_placeholders(self.instance.event, base_parameters).keys())]
        ht = _('Available placeholders: {list}').format(list=', '.join(phs))
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    class Meta:
        model = Voucher
        localized_fields = '__all__'
        fields = [
            'tag',
            'valid_until',
            'block_quota',
            'allow_ignore_quota',
            'allow_ignore_approval',
            'value',
            'comment',
            'max_usages',
            'price_mode',
            'subevent',
            'show_hidden_products',
            'budget',
        ]
        field_classes = {
            'valid_until': SplitDateTimeField,
            'subevent': SafeModelChoiceField,
        }
        widgets = {
            'valid_until': SplitDateTimePickerWidget(),
        }
        labels = {'max_usages': _('Maximum usages per voucher')}
        help_texts = {
            'tag': _('Vouchers with the same tag are shown together in the voucher list.'),
            'max_usages': _('Number of times EACH of these vouchers can be redeemed.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_field_placeholders('send_subject', ['event', 'name'])
        self._set_field_placeholders('send_message', ['event', 'voucher_list', 'name'])
        if 'seat' in self.fields:
            self.fields['seats'] = forms.CharField(
                label=_('Specific seat IDs'),
                required=False,
                widget=forms.Textarea(attrs={'data-seat-guid-field': '1'}),
                initial=self.instance.seat.seat_guid if self.instance.seat else '',
            )

    def clean_send_recipients(self):
        raw = self.cleaned_data['send_recipients']
        if not raw:
            return []
        r = raw.split('\n')
        res = []
        if ',' in raw or ';' in raw:
            if '@' in r[0]:
                raise ValidationError(_('CSV input needs to contain a header row in the first line.'))
            dialect = csv.Sniffer().sniff(raw[:1024])
            reader = csv.DictReader(StringIO(raw), dialect=dialect)
            if 'email' not in reader.fieldnames:
                raise ValidationError(
                    _('CSV input needs to contain a field with the header "{header}".').format(header='email')
                )
            unknown_fields = [f for f in reader.fieldnames if f not in ('email', 'name', 'tag', 'number')]
            if unknown_fields:
                raise ValidationError(
                    _('CSV input contains an unknown field with the header "{header}".').format(
                        header=unknown_fields[0]
                    )
                )
            for i, row in enumerate(reader):
                try:
                    EmailValidator()(row['email'])
                except ValidationError as err:
                    raise ValidationError(
                        _('{value} is not a valid email address.').format(value=row['email'])
                    ) from err
                try:
                    res.append(
                        self.Recipient(
                            name=row.get('name', ''),
                            email=row['email'].strip(),
                            number=int(row.get('number', 1)),
                            tag=row.get('tag', None),
                        )
                    )
                except ValueError as err:
                    raise ValidationError(_('Invalid value in row {number}.').format(number=i + 1)) from err
        else:
            for e in r:
                try:
                    EmailValidator()(e.strip())
                except ValidationError as err:
                    raise ValidationError(_('{value} is not a valid email address.').format(value=e.strip())) from err
                else:
                    res.append(self.Recipient(email=e.strip(), number=1, tag=None, name=''))
        return res

    def clean(self):
        data = super().clean()

        if data.get('use_tag_as_prefix'):
            tag = data.get('tag')
            if not tag:
                self.add_error('tag', _('A tag is required when it is used as a voucher code prefix.'))
            elif data.get('codes'):
                tag_upper = tag.upper()
                data['codes'] = [
                    code if code.upper().startswith(tag_upper) else f'{tag}{code}'
                    for code in data['codes']
                ]

        codes = data.get('codes', [])
        if data.get('use_tag_as_prefix') and codes:
            if len(codes) != len({code.upper() for code in codes}):
                self.add_error('codes', _('Voucher codes must be unique.'))
            elif any(len(code) > 255 for code in codes):
                self.add_error('codes', _('Voucher codes cannot be longer than 255 characters.'))

        if codes:
            vouchers = self.instance.event.vouchers.annotate(code_upper=Upper('code')).filter(
                code_upper__in=[code.upper() for code in codes]
            )
            if vouchers.exists():
                raise ValidationError(_('A voucher with one of these codes already exists.'))

        if data.get('send') and not all(
            [
                data.get('send_subject'),
                data.get('send_message'),
                data.get('send_recipients'),
            ]
        ):
            raise ValidationError(
                _('If vouchers should be sent by email, subject, message and recipients need to be specified.')
            )

        if codes and data.get('send'):
            recp = self.cleaned_data.get('send_recipients', [])
            code_len = len(codes)
            recp_len = sum(r.number for r in recp)
            if code_len != recp_len:
                raise ValidationError(
                    _('You generated {codes} vouchers, but entered recipients for {recp} vouchers.').format(
                        codes=code_len, recp=recp_len
                    )
                )

        if data.get('seats'):
            seatids = [s.strip() for s in data.get('seats').strip().split('\n') if s]
            if len(seatids) != len(codes):
                raise ValidationError(_('You need to specify as many seats as voucher codes.'))
            data['seats'] = []
            for s in seatids:
                data['seat'] = s
                data['seats'].append(
                    Voucher.clean_seat_id(
                        data,
                        self.instance.product,
                        self.instance.quota,
                        self.instance.event,
                        None,
                    )
                )
            self.instance.seat = data['seats'][0]  # Trick model-level validation
        else:
            data['seats'] = []

        return data

    def post_bulk_save(self, objs):
        for obj in objs:
            self._apply_product_limits(obj)
