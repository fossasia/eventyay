import csv
import io
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext as _

from eventyay.base.i18n import LazyLocaleException, language
from eventyay.base.models import (
    CachedFile,
    Event,
    InvoiceAddress,
    Order,
    OrderPayment,
    OrderPosition,
    User,
)
from eventyay.base.orderimport import NewImportProduct, NewImportVariation, ProductColumn, Variation, get_all_columns
from eventyay.base.services.invoices import generate_invoice, invoice_qualified
from eventyay.base.services.locking import LockTimeoutException
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.base.signals import order_paid, order_placed
from eventyay.celery_app import app


class DataImportError(LazyLocaleException):
    def __init__(self, *args):
        msg = args[0]
        msgargs = args[1] if len(args) > 1 else None
        self.args = args
        if msgargs:
            msg = _(msg) % msgargs
        else:
            msg = _(msg)
        super().__init__(msg)


def parse_csv(file, length=None):
    data = file.read(length)
    try:
        import chardet

        charset = chardet.detect(data)['encoding']
    except ImportError:
        charset = file.charset
    data = data.decode(charset or 'utf-8')
    # If the file was modified on a Mac, it only contains \r as line breaks
    if '\r' in data and '\n' not in data:
        data = data.replace('\r', '\n')

    try:
        dialect = csv.Sniffer().sniff(data.split('\n')[0], delimiters=';,.#:')
    except csv.Error:
        return None

    if dialect is None:
        return None

    reader = csv.DictReader(io.StringIO(data), dialect=dialect)
    return reader


def setif(record, obj, attr, setting):
    if setting.startswith('csv:'):
        setattr(obj, attr, record[setting[4:]] or '')


IMPORT_LOCK_TIMEOUT = 30


@app.task(
    base=ProfiledEventTask,
    bind=True,
    autoretry_for=(LockTimeoutException,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 5},
    throws=(DataImportError,),
)
def import_orders(self, event: Event, fileid: str, settings: dict, locale: str, user) -> None:
    # TODO: quotacheck?
    cf = CachedFile.objects.get(id=fileid)
    user = User.objects.get(pk=user)
    with language(locale, event.settings.region):
        cols = get_all_columns(event, settings)
        parsed = list(parse_csv(cf.file))
        data = []
        total = len(parsed)

        # Run validation
        for i, record in enumerate(parsed):
            if total > 0 and i % max(1, total // 10) == 0:
                self.update_state(state='PROGRESS', meta={'value': round(i / total * 25)})
            values = {}
            for c in cols:
                val = c.resolve(settings, record)
                try:
                    values[c.identifier] = c.clean(val, values)
                except ValidationError as e:
                    raise DataImportError(
                        _(
                            'Error while importing value "{value}" for column "{column}" in line "{line}": {message}'
                        ).format(
                            value=val if val is not None else '',
                            column=c.verbose_name,
                            line=i + 1,
                            message=e.message,
                        )
                    )
            data.append(values)

        product_columns = [c for c in cols if isinstance(c, ProductColumn)]
        variation_columns = [c for c in cols if isinstance(c, Variation)]
        orders = []

        # quota check?
        with event.lock(blocking=True, blocking_timeout=IMPORT_LOCK_TIMEOUT):
            with transaction.atomic():
                for column in product_columns:
                    try:
                        product_map = column.materialize_pending_products()
                    except ValidationError as e:
                        raise DataImportError(
                            _('Error while creating products: {message}').format(message=e.message)
                        )
                    for record in data:
                        product = record.get(column.identifier)
                        if isinstance(product, NewImportProduct):
                            record[column.identifier] = product_map[product.name]
                            
                for column in variation_columns:
                    try:
                        variation_map = column.materialize_pending_variations(product_map)
                    except ValidationError as e:
                        raise DataImportError(
                            _('Error while creating product variations: {message}').format(message=e.message)
                        )
                    for record in data:
                        variation = record.get(column.identifier)
                        if isinstance(variation, NewImportVariation):
                            key = (variation.value, variation.product_name, variation.product_id)
                            record[column.identifier] = variation_map[key]

                # Build and persist orders in the same transaction as product materialization so
                # newly created products are rolled back if the import fails.
                orders.clear()
                order = None
                for i, record in enumerate(data):
                    if total > 0 and i % max(1, total // 10) == 0:
                        self.update_state(state='PROGRESS', meta={'value': 25 + round(i / total * 25)})
                    try:
                        if order is None or settings['orders'] == 'many':
                            order = Order(
                                event=event,
                                testmode=settings['testmode'],
                            )
                            order.meta_info = {}
                            order._positions = []
                            order._address = InvoiceAddress()
                            order._address.name_parts = {'_scheme': event.settings.name_scheme}
                            orders.append(order)

                        position = OrderPosition(positionid=len(order._positions) + 1)
                        position.attendee_name_parts = {'_scheme': event.settings.name_scheme}
                        position.meta_info = {}
                        order._positions.append(position)
                        position.assign_pseudonymization_id()

                        for c in cols:
                            c.assign(record.get(c.identifier), order, position, order._address)

                    except ImportError as e:
                        raise ImportError(_('Invalid data in row {row}: {message}').format(row=i, message=str(e)))

                for i, o in enumerate(orders):
                    if len(orders) > 0 and i % max(1, len(orders) // 10) == 0:
                        self.update_state(state='PROGRESS', meta={'value': 50 + round(i / max(1, len(orders)) * 25)})
                    o.total = sum([c.price for c in o._positions])  # currently no support for fees
                    if o.total == Decimal('0.00'):
                        o.status = Order.STATUS_PAID
                        o.save()
                        OrderPayment.objects.create(
                            local_id=1,
                            order=o,
                            amount=Decimal('0.00'),
                            provider='free',
                            info='{}',
                            payment_date=now(),
                            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                        )
                    elif settings['status'] == 'paid':
                        o.status = Order.STATUS_PAID
                        o.save()
                        OrderPayment.objects.create(
                            local_id=1,
                            order=o,
                            amount=o.total,
                            provider='manual',
                            info='{}',
                            payment_date=now(),
                            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                        )
                    else:
                        o.status = Order.STATUS_PENDING
                        o.save()
                    for p in o._positions:
                        p.order = o
                        p.save()
                    o._address.order = o
                    o._address.save()
                    for c in cols:
                        c.save(o)
                    o.log_action(
                        'eventyay.event.order.placed',
                        user=user,
                        data={'source': 'import'},
                    )

        for i, o in enumerate(orders):
            if len(orders) > 0 and i % max(1, len(orders) // 10) == 0:
                self.update_state(state='PROGRESS', meta={'value': 75 + round(i / max(1, len(orders)) * 25)})
            with language(o.locale, event.settings.region):
                order_placed.send(event, order=o)
                if o.status == Order.STATUS_PAID:
                    order_paid.send(event, order=o)

                gen_invoice = (
                    invoice_qualified(o)
                    and (
                        (event.settings.get('invoice_generate') == 'True')
                        or (event.settings.get('invoice_generate') == 'paid' and o.status == Order.STATUS_PAID)
                    )
                    and not o.invoices.last()
                )
                if gen_invoice:
                    generate_invoice(o, trigger_pdf=True)
    cf.delete()
