import csv
import datetime
import io
from decimal import Decimal

import pytest
from zoneinfo import ZoneInfo
from django.utils.formats import date_format
from django.utils.timezone import now, override
from django_scopes import scope

from eventyay.base.models import (
    Checkin,
    Event,
    InvoiceAddress,
    Product as Item,
    Order,
    OrderPosition,
    Organizer,
)
from eventyay.plugins.checkinlists.exporters import CSVCheckinList, CheckinLogList


@pytest.fixture
def event():
    """Returns an event instance"""
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    with scope(organizer=o):
        event = Event.objects.create(
            organizer=o,
            name='Dummy',
            slug='dummy',
            date_from=now(),
            plugins='eventyay.plugins.checkinlists,tests.tickets.testdummy',
        )
        event.settings.set('attendee_names_asked', True)
        event.settings.set('name_scheme', 'title_given_middle_family')
        event.settings.set('locales', ['en', 'de'])
        event.checkin_lists.create(name='Default', all_products=True)

        order_paid = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            phone='+498912345678',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2019, 2, 22, 14, 0, 0, tzinfo=datetime.timezone.utc),
            expires=now() + datetime.timedelta(days=10),
            total=33,
            locale='en',
        )
        item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True)
        OrderPosition.objects.create(
            order=order_paid,
            product=item_ticket,
            variation=None,
            price=Decimal('23'),
            attendee_name_parts={
                'title': 'Mr',
                'given_name': 'Peter',
                'middle_name': 'A',
                'family_name': 'Jones',
            },
            secret='hutjztuxhkbtwnesv2suqv26k6ttytxx',
        )
        OrderPosition.objects.create(
            order=order_paid,
            product=item_ticket,
            variation=None,
            price=Decimal('13'),
            attendee_name_parts={
                'title': 'Mrs',
                'given_name': 'Andrea',
                'middle_name': 'J',
                'family_name': 'Zulu',
            },
            secret='ggsngqtnmhx74jswjngw3fk8pfwz2a7k',
        )
        yield event


def clean(d):
    return d.replace('\r', '').replace('\n', '')


@pytest.mark.django_db
def test_csv_simple(event):
    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title","Attendee name:
 First name","Attendee name: Middle name","Attendee name: Family name","Product","Price","Checked in","Checked out","Automatically
 checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special attention","Comment","Seat ID","Seat name",
"Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"FOO","Mr Peter A Jones","Mr","Peter","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"FOO","Mrs Andrea J Zulu","Mrs","Andrea","J","Zulu","Ticket","13.00","","","No","ggsngqtnmhx74jswjngw3fk8pfwz2a7k",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")


@pytest.mark.django_db
def test_csv_order_by_name_parts(event):  # noqa
    from django.conf import settings

    if not settings.JSON_FIELD_AVAILABLE:
        raise pytest.skip('Not supported on this database')
    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name:given_name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title",
"Attendee name: First name","Attendee name: Middle name","Attendee name: Family name","Product","Price",
"Checked in","Checked out","Automatically checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special
 attention","Comment","Seat ID","Seat name","Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"FOO","Mrs Andrea J Zulu","Mrs","Andrea","J","Zulu","Ticket","13.00","","","No","ggsngqtnmhx74jswjngw3fk8pfwz2a7k",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"FOO","Mr Peter A Jones","Mr","Peter","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")
    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name:family_name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title",
"Attendee name: First name","Attendee name: Middle name","Attendee name: Family name","Product","Price",
"Checked in","Checked out","Automatically checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special
 attention","Comment","Seat ID","Seat name","Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"FOO","Mr Peter A Jones","Mr","Peter","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"FOO","Mrs Andrea J Zulu","Mrs","Andrea","J","Zulu","Ticket","13.00","","","No","ggsngqtnmhx74jswjngw3fk8pfwz2a7k",
"dummy@dummy.test","'+498912345678","","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")


@pytest.mark.django_db
def test_csv_order_by_inherited_name_parts(event):  # noqa
    from django.conf import settings

    if not settings.JSON_FIELD_AVAILABLE:
        raise pytest.skip('Not supported on this database')

    with scope(organizer=event.organizer):
        OrderPosition.objects.filter(attendee_name_cached__icontains='Andrea').delete()
        op = OrderPosition.objects.get()
        op.attendee_name_parts = {}
        op.save()
        order2 = Order.objects.create(
            code='BAR',
            event=event,
            email='dummy@dummy.test',
            phone='+498912345678',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2019, 2, 22, 14, 0, 0, tzinfo=datetime.timezone.utc),
            expires=now() + datetime.timedelta(days=10),
            total=33,
            locale='en',
        )
        OrderPosition.objects.create(
            order=order2,
            item=event.items.first(),
            variation=None,
            company='BARCORP',
            price=Decimal('23'),
            secret='hutjztuxhkbtwnesv2suqv26k6ttytyy',
        )
        InvoiceAddress.objects.create(
            order=event.orders.get(code='BAR'),
            company='FOOCORP',
            name_parts={
                'title': 'Mr',
                'given_name': 'Albert',
                'middle_name': 'J',
                'family_name': 'Zulu',
                '_scheme': 'title_given_middle_family',
            },
        )
        InvoiceAddress.objects.create(
            order=event.orders.get(code='FOO'),
            company='FOOCORP',
            name_parts={
                'title': 'Mr',
                'given_name': 'Paul',
                'middle_name': 'A',
                'family_name': 'Jones',
                '_scheme': 'title_given_middle_family',
            },
        )

    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title",
"Attendee name: First name","Attendee name: Middle name","Attendee name: Family name","Product","Price",
"Checked in","Checked out","Automatically checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special
 attention","Comment","Seat ID","Seat name","Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"BAR","Mr Albert J Zulu","Mr","Albert","J","Zulu","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytyy",
"dummy@dummy.test","'+498912345678","BARCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"FOO","Mr Paul A Jones","Mr","Paul","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","FOOCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")
    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name:given_name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title",
"Attendee name: First name","Attendee name: Middle name","Attendee name: Family name","Product","Price",
"Checked in","Checked out","Automatically checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special
 attention","Comment","Seat ID","Seat name","Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"BAR","Mr Albert J Zulu","Mr","Albert","J","Zulu","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytyy",
"dummy@dummy.test","'+498912345678","BARCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"FOO","Mr Paul A Jones","Mr","Paul","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","FOOCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")
    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': event.checkin_lists.first().pk,
            'secrets': True,
            'sort': 'name:family_name',
            '_format': 'default',
            'questions': [],
        }
    )
    assert clean(content.decode()) == clean(""""Order code","Attendee name","Attendee name: Title",
"Attendee name: First name","Attendee name: Middle name","Attendee name: Family name","Product","Price",
"Checked in","Checked out","Automatically checked in","Secret","E-mail","Phone number","Company","Voucher code","Order date","Order time","Requires special
 attention","Comment","Seat ID","Seat name","Seat zone","Seat row","Seat number","Address","ZIP code","City","Country","State"
"FOO","Mr Paul A Jones","Mr","Paul","A","Jones","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytxx",
"dummy@dummy.test","'+498912345678","FOOCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
"BAR","Mr Albert J Zulu","Mr","Albert","J","Zulu","Ticket","23.00","","","No","hutjztuxhkbtwnesv2suqv26k6ttytyy",
"dummy@dummy.test","'+498912345678","BARCORP","","2019-02-22","14:00:00","No","","","","","","","","","","",""
""")


@pytest.mark.django_db
def test_csv_includes_all_checkins(event):
    cl = event.checkin_lists.first()
    with scope(organizer=event.organizer):
        op = OrderPosition.objects.get(secret='hutjztuxhkbtwnesv2suqv26k6ttytxx')
        Checkin.objects.create(
            position=op,
            list=cl,
            type=Checkin.TYPE_ENTRY,
            datetime=datetime.datetime(2019, 2, 22, 15, 0, 0, tzinfo=datetime.timezone.utc),
        )
        Checkin.objects.create(
            position=op,
            list=cl,
            type=Checkin.TYPE_ENTRY,
            datetime=datetime.datetime(2019, 2, 22, 16, 0, 0, tzinfo=datetime.timezone.utc),
        )

    c = CSVCheckinList(event)
    _, _, content = c.render(
        {
            'list': cl.pk,
            'secrets': False,
            'sort': 'name',
            '_format': 'default',
            'questions': [],
        }
    )
    csv_rows = list(csv.reader(io.StringIO(content.decode())))
    checked_in_index = csv_rows[0].index('Checked in')
    rows = [row for row in csv_rows[1:] if row[checked_in_index]]
    assert len(rows) == 2
    assert '2019-02-22' in rows[0][checked_in_index]
    assert '2019-02-22' in rows[1][checked_in_index]
    assert rows[0][checked_in_index] != rows[1][checked_in_index]


@pytest.mark.django_db
def test_checkinlog_includes_all_checkins(event):
    cl = event.checkin_lists.first()
    with scope(organizer=event.organizer):
        op = OrderPosition.objects.get(secret='hutjztuxhkbtwnesv2suqv26k6ttytxx')
        Checkin.objects.create(
            position=op,
            list=cl,
            type=Checkin.TYPE_ENTRY,
            datetime=datetime.datetime(2019, 2, 22, 15, 0, 0, tzinfo=datetime.timezone.utc),
        )
        Checkin.objects.create(
            position=op,
            list=cl,
            type=Checkin.TYPE_ENTRY,
            datetime=datetime.datetime(2019, 2, 22, 16, 0, 0, tzinfo=datetime.timezone.utc),
        )

    exporter = CheckinLogList(event)
    _, _, content = exporter.render(
        {
            'list': cl.pk,
            'products': [op.product_id],
            '_format': 'default',
        }
    )
    rows = [row for row in csv.reader(io.StringIO(content.decode())) if 'hutjztuxhkbtwnesv2suqv26k6ttytxx' in row]
    assert len(rows) == 2


@pytest.mark.django_db
def test_checkinlog_uses_event_timezone(event):
    with scope(organizer=event.organizer):
        event.timezone = 'Asia/Kolkata'
        event.save(update_fields=['timezone'])
        event = Event.objects.get(pk=event.pk)
        checked_at = datetime.datetime(2019, 2, 22, 23, 30, tzinfo=datetime.UTC)

        with scope(event=event):
            assert event.tz == ZoneInfo('Asia/Kolkata')
            cl = event.checkin_lists.first()
            op = OrderPosition.objects.get(secret='hutjztuxhkbtwnesv2suqv26k6ttytxx')
            Checkin.objects.create(
                position=op,
                list=cl,
                type=Checkin.TYPE_ENTRY,
                datetime=checked_at,
            )

            with override(ZoneInfo('UTC')):
                _, _, content = CheckinLogList(event).render(
                    {'list': cl.pk, 'products': [op.product_id], '_format': 'default'}
                )

    rows = list(csv.reader(io.StringIO(content.decode())))
    row = next(row for row in rows if 'hutjztuxhkbtwnesv2suqv26k6ttytxx' in row)
    event_datetime = checked_at.astimezone(ZoneInfo('Asia/Kolkata'))
    assert event_datetime == datetime.datetime(2019, 2, 23, 5, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    expected_date_and_time = [
        date_format(event_datetime, 'SHORT_DATE_FORMAT'),
        date_format(event_datetime, 'TIME_FORMAT'),
    ]
    assert expected_date_and_time == ['2019-02-23', '05:00']
    assert row[:2] == expected_date_and_time
