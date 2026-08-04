import datetime
import json
from decimal import Decimal

import dateutil.rrule
from django.db.models import Count, DateTimeField, Max, Min, OuterRef, Subquery
from django.utils import timezone
from eventyay.base.models import (
    Product,
    Order,
    OrderPayment,
    OrderPosition,
)
from eventyay.plugins.statistics.signals import clear_cache


def get_statistics_context(request, subevent=None):
    has_orders = request.event.orders.exists()
    if not has_orders:
        return {
            'stats_has_orders': False,
            'stats_obd_data': '[]',
            'stats_obp_data': '[]',
            'stats_rev_data': '[]',
            'stats_seats': {},
        }

    tz = timezone.get_current_timezone()

    if 'latest' in request.GET:
        clear_cache(request.event)

    cache = request.event.cache
    ckey = str(subevent.pk) if subevent else 'all'

    p_date = (
        OrderPayment.objects.filter(
            order=OuterRef('pk'),
            state__in=(
                OrderPayment.PAYMENT_STATE_CONFIRMED,
                OrderPayment.PAYMENT_STATE_REFUNDED,
            ),
            payment_date__isnull=False,
        )
        .values('order')
        .annotate(m=Max('payment_date'))
        .values('m')
        .order_by()
    )
    op_date = (
        OrderPayment.objects.filter(
            order=OuterRef('order'),
            state__in=(
                OrderPayment.PAYMENT_STATE_CONFIRMED,
                OrderPayment.PAYMENT_STATE_REFUNDED,
            ),
            payment_date__isnull=False,
        )
        .values('order')
        .annotate(m=Max('payment_date'))
        .values('m')
        .order_by()
    )

    # Orders by day
    obd_data = cache.get('statistics_obd_data' + ckey)
    if not obd_data:
        oqs = Order.objects.annotate(payment_date=Subquery(p_date, output_field=DateTimeField()))
        if subevent:
            oqs = oqs.filter(all_positions__subevent_id=subevent, all_positions__canceled=False).distinct()

        ordered_by_day = {}
        for o in oqs.filter(event=request.event).values('datetime'):
            day = o['datetime'].astimezone(tz).date()
            ordered_by_day[day] = ordered_by_day.get(day, 0) + 1
        paid_by_day = {}
        for o in oqs.filter(event=request.event, payment_date__isnull=False).values('payment_date'):
            day = o['payment_date'].astimezone(tz).date()
            paid_by_day[day] = paid_by_day.get(day, 0) + 1

        data = []
        for d in dateutil.rrule.rrule(
            dateutil.rrule.DAILY,
            dtstart=min(ordered_by_day.keys()) if ordered_by_day else datetime.date.today(),
            until=max(
                max(ordered_by_day.keys() if paid_by_day else [datetime.date.today()]),
                max(paid_by_day.keys() if paid_by_day else [datetime.date(1970, 1, 1)]),
            ),
        ):
            d = d.date()
            data.append(
                {
                    'date': d.strftime('%Y-%m-%d'),
                    'ordered': ordered_by_day.get(d, 0),
                    'paid': paid_by_day.get(d, 0),
                }
            )

        obd_data = json.dumps(data)
        cache.set('statistics_obd_data' + ckey, obd_data)

    # Orders by product
    obp_data = cache.get('statistics_obp_data' + ckey)
    if not obp_data:
        opqs = OrderPosition.objects
        if subevent:
            opqs = opqs.filter(subevent=subevent)
        num_ordered = {
            p['product']: p['cnt']
            for p in (
                opqs.filter(order__event=request.event).values('product').annotate(cnt=Count('id')).order_by()
            )
        }
        num_paid = {
            p['product']: p['cnt']
            for p in (
                opqs.filter(order__event=request.event, order__status=Order.STATUS_PAID)
                .values('product')
                .annotate(cnt=Count('id'))
                .order_by()
            )
        }
        product_names = {i.id: str(i) for i in Product.objects.filter(event=request.event)}
        obp_data = json.dumps(
            [
                {
                    'item': product_names[product],
                    'item_short': product_names[product] if len(product_names[product]) < 15 else (product_names[product][:15] + '…'),
                    'product': product_names[product],
                    'product_short': product_names[product] if len(product_names[product]) < 15 else (product_names[product][:15] + '…'),
                    'ordered': cnt,
                    'paid': num_paid.get(product, 0),
                }
                for product, cnt in num_ordered.items()
            ]
        )
        cache.set('statistics_obp_data' + ckey, obp_data)

    rev_data = cache.get('statistics_rev_data' + ckey)
    if not rev_data:
        rev_by_day = {}
        if subevent:
            for o in (
                OrderPosition.objects.annotate(payment_date=Subquery(op_date, output_field=DateTimeField()))
                .filter(
                    order__event=request.event,
                    subevent=subevent,
                    order__status=Order.STATUS_PAID,
                    payment_date__isnull=False,
                )
                .values('payment_date', 'price')
            ):
                day = o['payment_date'].astimezone(tz).date()
                rev_by_day[day] = rev_by_day.get(day, 0) + o['price']
        else:
            for o in (
                Order.objects.annotate(payment_date=Subquery(p_date, output_field=DateTimeField()))
                .filter(
                    event=request.event,
                    status=Order.STATUS_PAID,
                    payment_date__isnull=False,
                )
                .values('payment_date', 'total')
            ):
                day = o['payment_date'].astimezone(tz).date()
                rev_by_day[day] = rev_by_day.get(day, 0) + o['total']

        data = []
        total = 0
        for d in dateutil.rrule.rrule(
            dateutil.rrule.DAILY,
            dtstart=min(rev_by_day.keys() if rev_by_day else [datetime.date.today()]),
            until=max(rev_by_day.keys() if rev_by_day else [datetime.date.today()]),
        ):
            d = d.date()
            total += float(rev_by_day.get(d, 0))
            data.append(
                {
                    'date': d.strftime('%Y-%m-%d'),
                    'revenue': round(total, 2),
                }
            )
        rev_data = json.dumps(data)
        cache.set('statistics_rev_data' + ckey, rev_data)

    has_orders = request.event.orders.exists()
    seats = {}

    if not request.event.has_subevents or (ckey != 'all' and subevent):
        ev = subevent or request.event
        if ev.seating_plan_id is not None:
            seats_qs = ev.free_seats(sales_channel=None, include_blocked=True)
            seats['blocked_seats'] = seats_qs.filter(blocked=True).count()
            seats['free_seats'] = seats_qs.filter(blocked=False).count()
            seats['purchased_seats'] = (
                ev.seats.count() - seats['blocked_seats'] - seats['free_seats']
            )

            seats_qs = (
                seats_qs.values('product', 'blocked')
                .annotate(count=Count('id'))
                .order_by(
                    'product__category__position',
                    'product__position',
                    'product',
                    'blocked',
                )
            )

            seats['products'] = {}
            seats['stats'] = {}
            product_cache = {
                i.pk: i
                for i in request.event.products.annotate(has_variations=Count('variations')).filter(
                    pk__in={p['product'] for p in seats_qs if p['product']}
                )
            }
            product_cache[None] = None

            for product in seats_qs:
                product_obj = product_cache[product['product']]
                if product_obj not in seats['products']:
                    price = None
                    if product_obj and product_obj.has_variations:
                        price = product_obj.variations.filter(active=True).aggregate(Min('default_price'))[
                            'default_price__min'
                        ]
                    if product_obj and not price:
                        price = product_obj.default_price
                    if not price:
                        price = Decimal('0.00')

                    seats['products'][product_obj] = {
                        'free': {
                            'seats': 0,
                            'potential': Decimal('0.00'),
                        },
                        'blocked': {
                            'seats': 0,
                            'potential': Decimal('0.00'),
                        },
                        'price': price,
                    }
                data = seats['products'][product_obj]

                if product['blocked']:
                    data['blocked']['seats'] = product['count']
                    data['blocked']['potential'] = product['count'] * data['price']
                else:
                    data['free']['seats'] = product['count']
                    data['free']['potential'] = product['count'] * data['price']

    return {
        'stats_obd_data': obd_data,
        'stats_obp_data': obp_data,
        'stats_rev_data': rev_data,
        'stats_has_orders': has_orders,
        'stats_seats': seats,
    }
