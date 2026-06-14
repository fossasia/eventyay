import re
from collections import defaultdict
from decimal import Decimal, DecimalException

import pycountry
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import formats
from django.utils.functional import cached_property
from django.utils.translation import (
    gettext as _,
)
from django.utils.translation import (
    gettext_lazy,
    pgettext,
    pgettext_lazy,
)
from django_countries import countries
from django_countries.fields import Country
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.base.channels import get_all_sales_channels
from eventyay.base.forms.questions import guess_country
from eventyay.base.models import (
    OrderPosition,
    Product,
    ProductVariation,
    Quota,
    Question,
    QuestionAnswer,
    QuestionOption,
    Seat,
)
from eventyay.base.services.pricing import get_price
from eventyay.base.settings import (
    COUNTRIES_WITH_STATE_IN_ADDRESS,
    PERSON_NAME_SCHEMES,
)
from eventyay.base.import_utils import build_header_map, match_header, normalize_header_value, setting_is_truthy  # noqa: F401
from eventyay.base.signals import order_import_columns


class NewImportProduct:
    """Placeholder returned during validation when a product will be created on import."""

    __slots__ = ('name',)

    def __init__(self, name: str):
        self.name = name


def resolve_import_product(product):
    """Return a persisted Product or None when *product* is a pending import placeholder."""
    if isinstance(product, NewImportProduct):
        return None
    return product


class NewImportVariation:
    """Placeholder returned during validation when a variation will be created on import."""

    __slots__ = ('value', 'product_name', 'product_id')

    def __init__(self, value: str, product_name: str = None, product_id: str = None):
        self.value = value
        self.product_name = product_name
        self.product_id = product_id


def resolve_import_variation(variation):
    """Return a persisted ProductVariation or None when *variation* is a pending import placeholder."""
    if isinstance(variation, NewImportVariation):
        return None
    return variation


class ImportColumn:
    # Subclasses may override this with a list of CSV header name suggestions
    # used for automatic column matching when the import mapping form is first shown.
    suggestions = []

    @property
    def identifier(self):
        """
        Unique, internal name of the column.
        """
        raise NotImplementedError

    @property
    def verbose_name(self):
        """
        Human-readable description of the column
        """
        raise NotImplementedError

    @property
    def initial(self):
        """
        Initial value for the form component
        """
        return None

    @property
    def default_value(self):
        """
        Internal default value for the assignment of this column. Defaults to ``empty``. Return ``None`` to disable this
        option.
        """
        return 'empty'

    @property
    def default_label(self):
        """
        Human-readable description of the default assignment of this column, defaults to "Keep empty".
        """
        return gettext_lazy('Keep empty')

    def __init__(self, event):
        self.event = event

    def static_choices(self):
        """
        This will be called when rendering the form component and allows you to return a list of values that can be
        selected by the user statically during import.

        :return: list of 2-tuples of strings
        """
        return []

    def resolve(self, settings, record):
        """
        This method will be called to get the raw value for this field, usually by either using a static value or
        inspecting the CSV file for the assigned header. You usually do not need to implement this on your own,
        the default should be fine.
        """
        k = settings.get(self.identifier, self.default_value)
        if k == self.default_value:
            return None
        elif k.startswith('csv:'):
            return record.get(k[4:], None) or None
        elif k.startswith('static:'):
            return k[7:]
        raise ValidationError(_('Invalid setting for column "{header}".').format(header=self.verbose_name))

    def clean(self, value, previous_values):
        """
        Allows you to validate the raw input value for your column. Raise ``ValidationError`` if the value is invalid.
        You do not need to include the column or row name or value in the error message as it will automatically be
        included.

        :param value: Contains the raw value of your column as returned by ``resolve``. This can usually be ``None``,
                      e.g. if the column is empty or does not exist in this row.
        :param previous_values: Dictionary containing the validated values of all columns that have already been validated.
        """
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        """
        This will be called to perform the actual import. You are supposed to set attributes on the ``order``, ``position``,
        or ``invoice_address`` objects based on the input ``value``. This is called *before* the actual database
        transaction, so these three objects do not yet have a primary key. If you want to create related objects, you
        need to place them into some sort of internal queue and persist them when ``save`` is called.
        """
        pass

    def save(self, order):
        """
        This will be called to perform the actual import. This is called inside the actual database transaction and the
        input object ``order`` has already been saved to the database.
        """
        pass


class EmailColumn(ImportColumn):
    identifier = 'email'
    verbose_name = gettext_lazy('E-mail address')
    suggestions = ['email', 'e-mail', 'order email', 'customer email', 'email address']

    def clean(self, value, previous_values):
        if value:
            EmailValidator()(value)
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        order.email = value


class SubeventColumn(ImportColumn):
    identifier = 'subevent'
    verbose_name = pgettext_lazy('subevents', 'Date')
    default_value = None
    suggestions = ['date', 'subevent', 'sub-event', 'event date', 'subevent date']

    @cached_property
    def subevents(self):
        return list(self.event.subevents.filter(active=True).order_by('date_from'))

    def static_choices(self):
        return [(str(p.pk), str(p)) for p in self.subevents]

    def clean(self, value, previous_values):
        if not value:
            raise ValidationError(pgettext('subevent', 'You need to select a date.'))
        matches = [
            p
            for p in self.subevents
            if str(p.pk) == value
            or any((v and v == value) for v in i18n_flat(p.name))
            or p.date_from.isoformat() == value
        ]
        if len(matches) == 0:
            raise ValidationError(pgettext('subevent', 'No matching date was found.'))
        if len(matches) > 1:
            raise ValidationError(pgettext('subevent', 'Multiple matching dates were found.'))
        return matches[0]

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.subevent = value


def i18n_flat(l):
    if isinstance(l.data, dict):
        return l.data.values()
    return [l.data]


def find_matching_products(value, products):
    if not value:
        return []
    return [
        p
        for p in products
        if str(p.pk) == value
        or (p.internal_name and p.internal_name == value)
        or any((v and v == value) for v in i18n_flat(p.name))
    ]


def products_for_import_matching(event, *, create_missing: bool = False) -> list[Product]:
    """Products considered when resolving CSV product names during import."""
    qs = event.products.all()
    if not create_missing:
        qs = qs.filter(active=True)
    return list(qs)


def _count_raw_product_values(column, settings, records):
    """Count distinct raw CSV/static mapping values (strings), not cleaned Product objects."""
    counter = defaultdict(int)
    for record in records:
        val = column.resolve(settings, record)
        if val:
            counter[str(val)] += 1
    return counter


def collect_product_value_counts_by_header(fieldnames, records):
    """Count raw product values per CSV header in a single pass over *records*."""
    counters = {f'csv:{header}': defaultdict(int) for header in fieldnames}
    for record in records:
        for header in fieldnames:
            val = record.get(header)
            if val:
                counters[f'csv:{header}'][str(val)] += 1
    return counters


def _preview_items_from_counter(counter, products, create_missing):
    return [
        _preview_entry_for_value(value, count, products, create_missing)
        for value, count in sorted(counter.items())
    ]


def _preview_entry_for_value(value, row_count, products, create_missing):
    matches = find_matching_products(value, products)
    if len(matches) == 1:
        product = matches[0]
        return {
            'csv_value': value,
            'rows': row_count,
            'status': 'matched',
            'product_label': str(product),
            'product_id': product.pk,
        }
    if len(matches) > 1:
        return {
            'csv_value': value,
            'rows': row_count,
            'status': 'ambiguous',
            'product_label': ', '.join(str(p) for p in matches),
        }
    if create_missing:
        return {
            'csv_value': value,
            'rows': row_count,
            'status': 'create',
        }
    return {
        'csv_value': value,
        'rows': row_count,
        'status': 'missing',
    }


def build_product_preview_by_mapping(
    event,
    fieldnames,
    create_missing=False,
    records=None,
    csv_value_counts=None,
):
    products = products_for_import_matching(event, create_missing=create_missing)
    if csv_value_counts is None:
        csv_value_counts = collect_product_value_counts_by_header(fieldnames, records or [])

    by_mapping = {}
    for header in fieldnames:
        key = f'csv:{header}'
        by_mapping[key] = _preview_items_from_counter(
            csv_value_counts.get(key, {}),
            products,
            create_missing,
        )
    return by_mapping


def get_product_import_preview(
    event,
    settings,
    fieldnames=None,
    records=None,
    csv_value_counts=None,
    record_count=None,
):
    product_setting = settings.get('product')
    create_missing = setting_is_truthy(settings.get('create_missing_products'))
    fieldnames = fieldnames or []
    by_mapping = (
        build_product_preview_by_mapping(
            event,
            fieldnames,
            create_missing=create_missing,
            records=records,
            csv_value_counts=csv_value_counts,
        )
        if fieldnames
        else {}
    )

    if not product_setting or product_setting in (None, 'empty'):
        return {
            'unmapped': True,
            'create_missing': create_missing,
            'matched': [],
            'to_create': [],
            'missing': [],
            'ambiguous': [],
            'items': [],
            'by_mapping': by_mapping,
        }

    products = products_for_import_matching(event, create_missing=create_missing)
    if product_setting.startswith('static:'):
        static_value = product_setting[7:]
        rows = record_count if record_count is not None else len(records or [])
        items = [_preview_entry_for_value(static_value, rows, products, create_missing)]
    elif product_setting.startswith('csv:') and csv_value_counts is not None:
        values = csv_value_counts.get(product_setting, {})
        items = _preview_items_from_counter(values, products, create_missing)
    else:
        column = ProductColumn(event)
        values = _count_raw_product_values(column, {'product': product_setting}, records or [])
        items = _preview_items_from_counter(values, products, create_missing)

    return {
        'unmapped': False,
        'create_missing': create_missing,
        'product_mapping': product_setting,
        'matched': [i for i in items if i['status'] == 'matched'],
        'to_create': [i for i in items if i['status'] == 'create'],
        'missing': [i for i in items if i['status'] == 'missing'],
        'ambiguous': [i for i in items if i['status'] == 'ambiguous'],
        'items': items,
        'by_mapping': by_mapping,
    }


class ProductColumn(ImportColumn):
    identifier = 'product'
    verbose_name = gettext_lazy('Product')
    default_value = None
    suggestions = ['product', 'ticket', 'item', 'ticket type', 'product name']

    def __init__(self, event, create_missing: bool = False):
        self.create_missing = create_missing
        self._pending_product_names: set[str] = set()
        super().__init__(event)

    @cached_property
    def products(self) -> list[Product]:
        return products_for_import_matching(self.event, create_missing=self.create_missing)

    def static_choices(self):
        return [(str(p.pk), str(p)) for p in self.products]

    def clean(self, value, previous_values):
        matches = find_matching_products(value, self.products)
        if len(matches) == 0:
            if self.create_missing and value:
                self._pending_product_names.add(value)
                return NewImportProduct(value)
            raise ValidationError(_('No matching product was found.'))
        if len(matches) > 1:
            raise ValidationError(_('Multiple matching products were found.'))
        return matches[0]

    def materialize_pending_products(self) -> dict[str, Product]:
        if 'products' in self.__dict__:
            del self.__dict__['products']
        created: dict[str, Product] = {}
        products = products_for_import_matching(self.event, create_missing=True)
        for name in sorted(self._pending_product_names):
            matches = find_matching_products(name, products)
            if len(matches) == 1:
                created[name] = matches[0]
                continue
            if len(matches) > 1:
                raise ValidationError(_('Multiple matching products were found.'))
            with scope(event=self.event):
                product = Product.objects.create(
                    event=self.event,
                    name=LazyI18nString(name),
                    default_price=Decimal('0.00'),
                    active=False,
                    admission=True,
                    sales_channels=[],
                )
                quota = Quota.objects.create(
                    event=self.event,
                    name=name[:200],
                    size=None,
                )
                quota.products.add(product)
            products.append(product)
            created[name] = product
        self._pending_product_names.clear()
        return created

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.product = value


class Variation(ImportColumn):
    identifier = 'variation'
    verbose_name = gettext_lazy('Product variation')
    suggestions = ['variation', 'product variation', 'ticket variation', 'variant']

    def __init__(self, event, create_missing: bool = False):
        self.create_missing = create_missing
        self._pending_variations: set[tuple[str, str, str]] = set()
        super().__init__(event)

    @cached_property
    def products(self):
        qs = ProductVariation.objects.filter(product__event=self.event).select_related('product')
        if not self.create_missing:
            qs = qs.filter(active=True, product__active=True)
        return list(qs)

    def static_choices(self):
        return [(str(p.pk), f'{p.product} – {p.value}') for p in self.products]

    def clean(self, value, previous_values):
        raw_product = previous_values.get('product')
        product = resolve_import_product(raw_product)
        if value:
            if product is None:
                if self.create_missing and isinstance(raw_product, NewImportProduct):
                    self._pending_variations.add((value, raw_product.name, None))
                    return NewImportVariation(value, product_name=raw_product.name)
                raise ValidationError(_('No matching variation was found.'))

            matches = [
                p
                for p in self.products
                if (str(p.pk) == value
                or any((v and v == value) for v in i18n_flat(p.value)))
                and p.product_id == product.pk
            ]
            if len(matches) == 0:
                if self.create_missing:
                    self._pending_variations.add((value, None, str(product.pk)))
                    return NewImportVariation(value, product_id=str(product.pk))
                raise ValidationError(_('No matching variation was found.'))
            if len(matches) > 1:
                raise ValidationError(_('Multiple matching variations were found.'))
            return matches[0]
        elif product is not None and product.variations.exists():
            raise ValidationError(_('You need to select a variation for this product.'))
        return value

    def materialize_pending_variations(self, product_map: dict[str, Product]) -> dict[tuple[str, str, str], ProductVariation]:
        if 'products' in self.__dict__:
            del self.__dict__['products']
        created: dict[tuple[str, str, str], ProductVariation] = {}
        for pending_var in sorted(self._pending_variations):
            val, p_name, p_id = pending_var
            
            if p_id is not None:
                product = Product.objects.get(pk=p_id, event=self.event)
            else:
                product = product_map.get(p_name)
                if not product:
                    raise ValidationError(_('Product for variation not found.'))

            matches = [
                p
                for p in self.products
                if (str(p.pk) == val
                or any((v and v == val) for v in i18n_flat(p.value)))
                and p.product_id == product.pk
            ]
            if len(matches) == 1:
                created[pending_var] = matches[0]
                continue
            if len(matches) > 1:
                raise ValidationError(_('Multiple matching variations were found.'))

            with scope(event=self.event):
                variation = ProductVariation.objects.create(
                    product=product,
                    value=LazyI18nString(val),
                    active=False,
                    default_price=None,
                )
            self.products.append(variation)
            created[pending_var] = variation

        self._pending_variations.clear()
        return created

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.variation = value


class InvoiceAddressCompany(ImportColumn):
    identifier = 'invoice_address_company'
    suggestions = ['invoice address: company', 'invoice company', 'billing company', 'company']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('Company')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.company = value or ''
        invoice_address.is_business = bool(value)


class InvoiceAddressNamePart(ImportColumn):
    def __init__(self, event, key, label):
        self.key = key
        self.label = label
        super().__init__(event)

    @property
    def suggestions(self):
        label_lower = str(self.label).lower()
        key_with_spaces = self.key.lower().replace('_', ' ')
        return [
            f'invoice address name: {label_lower}',
            f'invoice address name: {key_with_spaces}',
            f'invoice {label_lower}',
            f'invoice {key_with_spaces}',
        ]

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + str(self.label)

    @property
    def identifier(self):
        return f'invoice_address_name_{self.key}'

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.name_parts[self.key] = value or ''


class InvoiceAddressStreet(ImportColumn):
    identifier = 'invoice_address_street'
    suggestions = ['invoice address: address', 'billing address', 'invoice street', 'billing street', 'address', 'street']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('Address')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.address = value or ''


class InvoiceAddressZip(ImportColumn):
    identifier = 'invoice_address_zipcode'
    suggestions = ['invoice address: zip code', 'billing zip code', 'billing postal code', 'invoice zip code', 'zip code', 'zip', 'postal code', 'postcode']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('ZIP code')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.zipcode = value or ''


class InvoiceAddressCity(ImportColumn):
    identifier = 'invoice_address_city'
    suggestions = ['invoice address: city', 'billing city', 'invoice city', 'city', 'town']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('City')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.city = value or ''


class InvoiceAddressCountry(ImportColumn):
    identifier = 'invoice_address_country'
    default_value = None
    suggestions = ['invoice address: country', 'billing country', 'invoice country', 'country']

    @property
    def initial(self):
        return 'static:' + str(guess_country(self.event))

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('Country')

    def static_choices(self):
        return list(countries)

    def clean(self, value, previous_values):
        if value and not Country(value).numeric:
            raise ValidationError(_('Please enter a valid country code.'))
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.country = value or ''


class InvoiceAddressState(ImportColumn):
    identifier = 'invoice_address_state'
    suggestions = ['invoice address: state', 'billing state', 'invoice state', 'state', 'province']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + pgettext('address', 'State')

    def clean(self, value, previous_values):
        if value:
            if previous_values.get('invoice_address_country') not in COUNTRIES_WITH_STATE_IN_ADDRESS:
                raise ValidationError(_('States are not supported for this country.'))

            types, form = COUNTRIES_WITH_STATE_IN_ADDRESS[previous_values.get('invoice_address_country')]
            match = [
                s
                for s in pycountry.subdivisions.get(country_code=previous_values.get('invoice_address_country'))
                if s.type in types and (s.code[3:] == value or s.name == value)
            ]
            if len(match) == 0:
                raise ValidationError(_('Please enter a valid state.'))
            return match[0].code[3:]

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.state = value or ''


class InvoiceAddressVATID(ImportColumn):
    identifier = 'invoice_address_vat_id'
    suggestions = ['vat id', 'vat', 'tax id', 'invoice vat id']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('VAT ID')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.vat_id = value or ''


class InvoiceAddressReference(ImportColumn):
    identifier = 'invoice_address_internal_reference'
    suggestions = ['internal reference', 'reference', 'invoice reference']

    @property
    def verbose_name(self):
        return _('Invoice address') + ': ' + _('Internal reference')

    def assign(self, value, order, position, invoice_address, **kwargs):
        invoice_address.internal_reference = value or ''


class AttendeeNamePart(ImportColumn):
    def __init__(self, event, key, label):
        self.key = key
        self.label = label
        super().__init__(event)

    @property
    def suggestions(self):
        label_lower = str(self.label).lower()
        key_with_spaces = self.key.lower().replace('_', ' ')
        return [
            f'attendee name: {label_lower}',
            f'attendee name: {key_with_spaces}',
            f'attendee {label_lower}',
            f'attendee {key_with_spaces}',
            label_lower,
            key_with_spaces,
        ]

    @property
    def verbose_name(self):
        return _('Attendee name') + ': ' + str(self.label)

    @property
    def identifier(self):
        return f'attendee_name_{self.key}'

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.attendee_name_parts[self.key] = value or ''


class AttendeeEmail(ImportColumn):
    identifier = 'attendee_email'
    verbose_name = gettext_lazy('Attendee e-mail address')
    suggestions = ['attendee email', 'attendee e-mail', 'attendee email address']

    def clean(self, value, previous_values):
        if value:
            EmailValidator()(value)
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.attendee_email = value


class AttendeeCompany(ImportColumn):
    identifier = 'attendee_company'
    suggestions = ['company', 'attendee company', 'organization', 'organisation']

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('Company')

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.company = value or ''


class AttendeeJobTitle(ImportColumn):
    identifier = 'job_title'
    suggestions = ['job title', 'title', 'position', 'role', 'occupation']

    @property
    def verbose_name(self):
        return _('Attendee Job Title') + ': ' + _('Job Title')

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.job_title = value or ''


class AttendeeStreet(ImportColumn):
    identifier = 'attendee_street'
    suggestions = ['address', 'street', 'street address', 'attendee address']

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('Address')

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.street = value or ''


class AttendeeZip(ImportColumn):
    identifier = 'attendee_zipcode'
    suggestions = ['zip code', 'zip', 'postal code', 'postcode']

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('ZIP code')

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.zipcode = value or ''


class AttendeeCity(ImportColumn):
    identifier = 'attendee_city'
    suggestions = ['city', 'attendee city', 'town']

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('City')

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.city = value or ''


class AttendeeCountry(ImportColumn):
    identifier = 'attendee_country'
    default_value = None
    suggestions = ['country', 'attendee country']

    @property
    def initial(self):
        return 'static:' + str(guess_country(self.event))

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('Country')

    def static_choices(self):
        return list(countries)

    def clean(self, value, previous_values):
        if value and not Country(value).numeric:
            raise ValidationError(_('Please enter a valid country code.'))
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.country = value or ''


class AttendeeState(ImportColumn):
    identifier = 'attendee_state'
    suggestions = ['state', 'province', 'region', 'attendee state']

    @property
    def verbose_name(self):
        return _('Attendee address') + ': ' + _('State')

    def clean(self, value, previous_values):
        if value:
            if previous_values.get('attendee_country') not in COUNTRIES_WITH_STATE_IN_ADDRESS:
                raise ValidationError(_('States are not supported for this country.'))

            types, form = COUNTRIES_WITH_STATE_IN_ADDRESS[previous_values.get('attendee_country')]
            match = [
                s
                for s in pycountry.subdivisions.get(country_code=previous_values.get('attendee_country'))
                if s.type in types and (s.code[3:] == value or s.name == value)
            ]
            if len(match) == 0:
                raise ValidationError(_('Please enter a valid state.'))
            return match[0].code[3:]

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.state = value or ''


class Price(ImportColumn):
    identifier = 'price'
    verbose_name = gettext_lazy('Price')
    default_label = gettext_lazy('Calculate from product')
    suggestions = ['price', 'amount', 'cost', 'total', 'net price']

    def clean(self, value, previous_values):
        if value not in (None, ''):
            value = formats.sanitize_separators(re.sub(r'[^0-9.,-]', '', value))
            try:
                value = Decimal(value)
            except (DecimalException, TypeError):
                raise ValidationError(_('You entered an invalid number.'))
            return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        if value is None:
            p = get_price(
                position.product,
                position.variation,
                position.voucher,
                subevent=position.subevent,
                invoice_address=invoice_address,
            )
        else:
            p = get_price(
                position.product,
                position.variation,
                position.voucher,
                subevent=position.subevent,
                invoice_address=invoice_address,
                custom_price=value,
                force_custom_price=True,
            )
        position.price = p.gross
        position.tax_rule = position.product.tax_rule
        position.tax_rate = p.rate
        position.tax_value = p.tax


class Secret(ImportColumn):
    identifier = 'secret'
    verbose_name = gettext_lazy('Ticket code')
    default_label = gettext_lazy('Generate automatically')
    suggestions = ['secret', 'ticket code', 'barcode', 'ticket secret']

    def __init__(self, *args):
        self._cached = set()
        super().__init__(*args)

    def clean(self, value, previous_values):
        if value and (
            value in self._cached or OrderPosition.all.filter(order__event=self.event, secret=value).exists()
        ):
            raise ValidationError(_('You cannot assign a position secret that already exists.'))
        self._cached.add(value)
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        if value:
            position.secret = value


class Locale(ImportColumn):
    identifier = 'locale'
    verbose_name = gettext_lazy('Order locale')
    default_value = None
    suggestions = ['locale', 'order locale', 'language', 'order language']

    @property
    def initial(self):
        return 'static:' + self.event.settings.locale

    def static_choices(self):
        locale_names = dict(settings.LANGUAGES)
        return [(a, locale_names[a]) for a in self.event.settings.locales]

    def clean(self, value, previous_values):
        if not value:
            value = self.event.settings.locale
        if value not in self.event.settings.locales:
            raise ValidationError(_('Please enter a valid language code.'))
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        order.locale = value


class Saleschannel(ImportColumn):
    identifier = 'sales_channel'
    verbose_name = gettext_lazy('Sales channel')
    suggestions = ['sales channel', 'channel', 'sale channel']

    def static_choices(self):
        return [(sc.identifier, sc.verbose_name) for sc in get_all_sales_channels().values()]

    def clean(self, value, previous_values):
        if not value:
            value = 'web'
        if value not in get_all_sales_channels():
            raise ValidationError(_('Please enter a valid sales channel.'))
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        order.sales_channel = value


class SeatColumn(ImportColumn):
    identifier = 'seat'
    verbose_name = gettext_lazy('Seat ID')
    suggestions = ['seat id', 'seat', 'seat number', 'seat guid']

    def __init__(self, *args):
        self._cached = set()
        super().__init__(*args)

    def clean(self, value, previous_values):
        if value:
            try:
                value = Seat.objects.get(seat_guid=value, subevent=previous_values.get('subevent'))
            except Seat.DoesNotExist:
                raise ValidationError(_('No matching seat was found.'))
            if not value.is_available() or value in self._cached:
                raise ValidationError(
                    _('The seat you selected has already been taken. Please select a different seat.')
                )
            self._cached.add(value)
        else:
            product = resolve_import_product(previous_values.get('product'))
            if (
                product is not None
                and product.seat_category_mappings.filter(subevent=previous_values.get('subevent')).exists()
            ):
                raise ValidationError(_('You need to select a specific seat.'))
        return value

    def assign(self, value, order, position, invoice_address, **kwargs):
        position.seat = value


class Comment(ImportColumn):
    identifier = 'comment'
    verbose_name = gettext_lazy('Comment')
    suggestions = ['comment', 'order comment', 'notes', 'remarks', 'order notes']

    def assign(self, value, order, position, invoice_address, **kwargs):
        order.comment = value or ''


class QuestionColumn(ImportColumn):
    def __init__(self, event, q):
        self.q = q
        self.option_resolve_cache = defaultdict(set)

        for opt in q.options.all():
            self.option_resolve_cache[str(opt.id)].add(opt)
            self.option_resolve_cache[opt.identifier].add(opt)

            if isinstance(opt.answer, LazyI18nString):
                if isinstance(opt.answer.data, dict):
                    for v in opt.answer.data.values():
                        self.option_resolve_cache[v.strip()].add(opt)
                else:
                    self.option_resolve_cache[opt.answer.data.strip()].add(opt)

            else:
                self.option_resolve_cache[opt.answer.strip()].add(opt)
        super().__init__(event)

    @property
    def suggestions(self):
        return [str(self.q.question)]

    @property
    def verbose_name(self):
        return _('Question') + ': ' + str(self.q.question)

    @property
    def identifier(self):
        return f'question_{self.q.pk}'

    def clean(self, value, previous_values):
        if value:
            if self.q.type in Question.SINGLE_CHOICE_TYPES:
                if value not in self.option_resolve_cache:
                    raise ValidationError(_('Invalid option selected.'))
                if len(self.option_resolve_cache[value]) > 1:
                    raise ValidationError(_('Ambiguous option selected.'))
                return list(self.option_resolve_cache[value])[0]

            elif self.q.type == Question.TYPE_CHOICE_MULTIPLE:
                values = value.split(',')
                if any(v.strip() not in self.option_resolve_cache for v in values):
                    raise ValidationError(_('Invalid option selected.'))
                if any(len(self.option_resolve_cache[v.strip()]) > 1 for v in values):
                    raise ValidationError(_('Ambiguous option selected.'))
                return [list(self.option_resolve_cache[v.strip()])[0] for v in values]

            else:
                return self.q.clean_answer(value)

    def assign(self, value, order, position, invoice_address, **kwargs):
        if value:
            if not hasattr(order, '_answers'):
                order._answers = []
            if isinstance(value, QuestionOption):
                a = QuestionAnswer(orderposition=position, question=self.q, answer=str(value))
                a._options = [value]
                order._answers.append(a)
            elif isinstance(value, list):
                a = QuestionAnswer(
                    orderposition=position,
                    question=self.q,
                    answer=', '.join(str(v) for v in value),
                )
                a._options = value
                order._answers.append(a)
            else:
                order._answers.append(QuestionAnswer(question=self.q, answer=str(value), orderposition=position))

    def save(self, order):
        for a in getattr(order, '_answers', []):
            a.orderposition = a.orderposition  # This is apparently required after save() again
            a.save()
            if hasattr(a, '_options'):
                a.options.add(*a._options)


def get_all_columns(event, settings: dict | None = None):
    create_missing = setting_is_truthy(settings.get('create_missing_products')) if settings else False
    default = []
    if event.has_subevents:
        default.append(SubeventColumn(event))
    default += [
        EmailColumn(event),
        ProductColumn(event, create_missing=create_missing),
        Variation(event, create_missing=create_missing),
        InvoiceAddressCompany(event),
    ]
    scheme = PERSON_NAME_SCHEMES.get(event.settings.name_scheme)
    for n, l, w in scheme['fields']:
        default.append(InvoiceAddressNamePart(event, n, l))
    default += [
        InvoiceAddressStreet(event),
        InvoiceAddressZip(event),
        InvoiceAddressCity(event),
        InvoiceAddressCountry(event),
        InvoiceAddressState(event),
        InvoiceAddressVATID(event),
        InvoiceAddressReference(event),
    ]
    for n, l, w in scheme['fields']:
        default.append(AttendeeNamePart(event, n, l))
    default += [
        AttendeeEmail(event),
        AttendeeCompany(event),
        AttendeeJobTitle(event),
        AttendeeStreet(event),
        AttendeeZip(event),
        AttendeeCity(event),
        AttendeeCountry(event),
        AttendeeState(event),
        Price(event),
        Secret(event),
        Locale(event),
        Saleschannel(event),
        SeatColumn(event),
        Comment(event),
    ]
    for q in event.questions.prefetch_related('options').exclude(type=Question.TYPE_FILE):
        default.append(QuestionColumn(event, q))

    for recv, resp in order_import_columns.send(sender=event):
        default += resp

    return default
