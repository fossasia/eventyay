import json
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytz
from django.db.models import Exists, OuterRef, Q
from django.template.loader import get_template
from django.utils.encoding import force_str
from django.utils.translation import gettext as _

from eventyay import __version__
from eventyay.base.models import Event, EventMetaValue, SubEvent, SubEventMetaValue
from eventyay.multidomain.urlreverse import build_absolute_uri, eventreverse


def get_organizer_export_events(request):
    """Events and sub-events included in organizer calendar exports."""
    organizer = request.organizer
    channel = request.sales_channel.identifier

    events = list(
        filter_qs_by_attr(
            organizer.events.filter(
                is_public=True,
                live=True,
                has_subevents=False,
                sales_channels__contains=channel,
            ),
            request,
            use_session=False,
        )
        .order_by('date_from')
        .prefetch_related('_settings_objects', 'organizer___settings_objects')
    )
    events += list(
        filter_qs_by_attr(
            SubEvent.objects.filter(
                event__organizer=organizer,
                event__is_public=True,
                event__live=True,
                is_public=True,
                active=True,
                event__sales_channels__contains=channel,
            ),
            request,
            use_session=False,
        )
        .prefetch_related('event___settings_objects', 'event__organizer___settings_objects')
        .order_by('date_from')
    )
    return events


def _event_entry(ev):
    event = ev if isinstance(ev, Event) else ev.event
    tz = pytz.timezone(event.settings.timezone)
    start = ev.date_from.astimezone(tz)
    end = ev.date_to.astimezone(tz) if event.settings.show_date_to and ev.date_to else start + timedelta(hours=1)
    start_utc = ev.date_from.astimezone(pytz.utc)
    end_utc = ev.date_to.astimezone(pytz.utc) if event.settings.show_date_to and ev.date_to else start_utc + timedelta(hours=1)

    if isinstance(ev, Event):
        url = build_absolute_uri(event, 'presale:event.index')
        slug = event.slug
        uid = f'{event.organizer.slug}-{event.slug}-0'
    else:
        url = build_absolute_uri(event, 'presale:event.index', {'subevent': ev.pk})
        slug = f'{event.slug}-{ev.pk}'
        uid = f'{event.organizer.slug}-{event.slug}-{ev.pk}'

    duration_mins = max(int((end - start).total_seconds() // 60), 5)
    export_duration = f'{duration_mins // 60:02d}:{duration_mins % 60:02d}'
    pentabarf_duration = f'PT{duration_mins // 60}H{duration_mins % 60}M0S'

    return {
        'ev': ev,
        'event': event,
        'name': str(ev.name),
        'start': start,
        'end': end,
        'start_utc': start_utc,
        'end_utc': end_utc,
        'url': url,
        'slug': slug,
        'uid': uid,
        'export_duration': export_duration,
        'pentabarf_export_duration': pentabarf_duration,
        'location': str(ev.location) if getattr(ev, 'location', None) else '',
    }


def build_organizer_frab_data(organizer, events, base_url):
    """Build frab-compatible day/room/event structure for organizer ticket events."""
    by_date = defaultdict(list)
    date_bounds = {}

    for ev in events:
        entry = _event_entry(ev)
        day = entry['start'].date()
        by_date[day].append(entry)
        if day not in date_bounds:
            date_bounds[day] = {'start': entry['start'], 'end': entry['end']}
        else:
            if entry['start'] < date_bounds[day]['start']:
                date_bounds[day]['start'] = entry['start']
            if entry['end'] > date_bounds[day]['end']:
                date_bounds[day]['end'] = entry['end']

    if not by_date:
        today = datetime.now(pytz.utc).date()
        by_date[today] = []
        date_bounds[today] = {
            'start': datetime.combine(today, datetime.min.time()).replace(tzinfo=pytz.utc),
            'end': datetime.combine(today, datetime.max.time()).replace(tzinfo=pytz.utc),
        }

    days = []
    room_name = force_str(_('Events'))
    room_guid = f'{organizer.slug}-events'

    for index, day_date in enumerate(sorted(by_date.keys()), start=1):
        bounds = date_bounds[day_date]
        day_start = bounds['start'].replace(hour=4, minute=0, second=0, microsecond=0)
        if bounds['start'].hour < 3:
            day_start = (bounds['start'] - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1) - timedelta(minutes=1)

        days.append(
            {
                'index': index,
                'start': day_start,
                'end': day_end,
                'rooms': [
                    {
                        'name': room_name,
                        'guid': room_guid,
                        'entries': sorted(by_date[day_date], key=lambda e: e['start']),
                    }
                ],
            }
        )

    all_starts = [e['start'] for d in days for r in d['rooms'] for e in r['entries']]
    all_ends = [e['end'] for d in days for r in d['rooms'] for e in r['entries']]
    conf_start = min(all_starts) if all_starts else datetime.now(pytz.utc)
    conf_end = max(all_ends) if all_ends else conf_start

    return {
        'url': base_url,
        'version': '1',
        'base_url': base_url,
        'organizer': organizer,
        'conference': {
            'acronym': organizer.slug,
            'title': str(organizer.name),
            'start': conf_start,
            'end': conf_end,
            'duration': max((conf_end.date() - conf_start.date()).days + 1, 1),
            'timezone': str(conf_start.tzinfo or 'UTC'),
        },
        'days': days,
        'domain': urlparse(base_url).netloc,
    }


def render_organizer_json(organizer, events, base_url):
    data = build_organizer_frab_data(organizer, events, base_url)
    conf = data['conference']
    payload = {
        '$schema': 'https://c3voc.de/schedule/schema.json',
        'generator': {'name': 'eventyay', 'version': __version__},
        'url': data['url'],
        'version': data['version'],
        'base_url': data['base_url'],
        'conference': {
            'acronym': conf['acronym'],
            'title': conf['title'],
            'start': f"{conf['start']:%Y-%m-%d}",
            'end': f"{conf['end']:%Y-%m-%d}",
            'daysCount': conf['duration'],
            'timeslot_duration': '00:05',
            'time_zone_name': conf['timezone'],
            'rooms': [
                {
                    'name': str(data['days'][0]['rooms'][0]['name']) if data['days'] else force_str(_('Events')),
                    'slug': 'events',
                    'guid': f'{organizer.slug}-events',
                }
            ],
            'tracks': [],
            'days': [
                {
                    'index': day['index'],
                    'date': f"{day['start']:%Y-%m-%d}",
                    'day_start': day['start'].isoformat(),
                    'day_end': day['end'].isoformat(),
                    'rooms': {
                        room['guid']: [
                            {
                                'guid': entry['uid'],
                                'code': entry['slug'],
                                'title': entry['name'],
                                'slug': entry['slug'],
                                'url': entry['url'],
                                'date': entry['start'].isoformat(),
                                'start': entry['start'].strftime('%H:%M'),
                                'duration': entry['export_duration'],
                                'room': str(room['name']),
                                'track': None,
                                'type': force_str(_('Event')),
                            }
                            for entry in room['entries']
                        ]
                        for room in day['rooms']
                    },
                }
                for day in data['days']
            ],
        },
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'{organizer.slug}-events.json', 'application/json', content


def render_organizer_xml(organizer, events, base_url):
    data = build_organizer_frab_data(organizer, events, base_url)
    content = get_template('pretixpresale/organizers/events.xml').render(
        {'data': data, 'version': __version__}
    )
    return f'{organizer.slug}-events.xml', 'text/xml', content


def render_organizer_xcal(organizer, events, base_url):
    data = build_organizer_frab_data(organizer, events, base_url)
    content = get_template('pretixpresale/organizers/events.xcal').render({'data': data})
    return f'{organizer.slug}.xcal', 'text/xml', content


def render_organizer_export(organizer, events, export_name, base_url):
    if export_name == 'schedule.json':
        return render_organizer_json(organizer, events, base_url)
    if export_name == 'schedule.xml':
        return render_organizer_xml(organizer, events, base_url)
    if export_name == 'schedule.xcal':
        return render_organizer_xcal(organizer, events, base_url)
    return None


def filter_qs_by_attr(qs, request, use_session=True):
    """
    We'll allow to filter the event list using attributes defined in the event meta data
    models in the format ?attr[meta_name]=meta_value
    """
    if not getattr(request, 'organizer', None):
        return qs

    attrs = {}
    for i, item in enumerate(request.GET.items()):
        k, v = item
        if k.startswith('attr[') and k.endswith(']'):
            attrs[k[5:-1]] = v

    skey = 'filter_qs_by_attr_{}_{}'.format(request.organizer.pk, request.event.pk if hasattr(request, 'event') else '')
    if use_session and request.GET.get('attr_persist'):
        request.session[skey] = attrs
    elif use_session and skey in request.session:
        attrs = request.session[skey]

    props = {p.name: p for p in request.organizer.meta_properties.filter(name__in=attrs.keys())}

    for i, item in enumerate(attrs.items()):
        attr, v = item
        emv_with_value = EventMetaValue.objects.filter(
            event=OuterRef('event' if qs.model == SubEvent else 'pk'),
            property__name=attr,
            value=v,
        )
        emv_with_any_value = EventMetaValue.objects.filter(
            event=OuterRef('event' if qs.model == SubEvent else 'pk'),
            property__name=attr,
        )
        if qs.model == SubEvent:
            semv_with_value = SubEventMetaValue.objects.filter(subevent=OuterRef('pk'), property__name=attr, value=v)
            semv_with_any_value = SubEventMetaValue.objects.filter(
                subevent=OuterRef('pk'),
                property__name=attr,
            )

        prop = props.get(attr)
        if not prop:
            continue
        annotations = {'attr_{}'.format(i): Exists(emv_with_value)}
        if qs.model == SubEvent:
            annotations['attr_{}_sub'.format(i)] = Exists(semv_with_value)
            annotations['attr_{}_sub_any'.format(i)] = Exists(semv_with_any_value)
            filters = Q(**{'attr_{}_sub'.format(i): True})
            filters |= Q(Q(**{'attr_{}_sub_any'.format(i): False}) & Q(**{'attr_{}'.format(i): True}))
            if prop.default == v:
                annotations['attr_{}_any'.format(i)] = Exists(emv_with_any_value)
                filters |= Q(Q(**{'attr_{}_sub_any'.format(i): False}) & Q(**{'attr_{}_any'.format(i): False}))
        else:
            filters = Q(**{'attr_{}'.format(i): True})
            if prop.default == v:
                annotations['attr_{}_any'.format(i)] = Exists(emv_with_any_value)
                filters |= Q(**{'attr_{}_any'.format(i): False})

        qs = qs.annotate(**annotations).filter(filters)
    return qs


def build_organizer_calendar_exporters(request):
    """Export links for organizer list/week/month views (aligned with agenda schedule)."""
    organizer = request.organizer
    query_string = request.GET.urlencode()
    query_suffix = f'?{query_string}' if query_string else ''

    locale_params = request.GET.copy()
    locale_params['locale'] = request.LANGUAGE_CODE
    locale_params.pop('page', None)
    ical_path = eventreverse(organizer, 'presale:organizer.ical')
    if locale_params:
        ical_path = f'{ical_path}?{locale_params.urlencode()}'

    def export_url(name):
        return (
            eventreverse(organizer, 'presale:organizer.events.export', kwargs={'name': name})
            + query_suffix
        )

    webcal_params = request.GET.copy()
    webcal_params['locale'] = request.LANGUAGE_CODE
    webcal_params.pop('page', None)
    webcal_suffix = f'?{webcal_params.urlencode()}' if webcal_params else ''

    return [
        {
            'icon': 'fa-google',
            'label': _('Subscribe to Google Calendar'),
            'url': eventreverse(
                organizer,
                'presale:organizer.export',
                kwargs={'export_target': 'google-calendar'},
            )
            + query_suffix,
        },
        {
            'icon': 'fa-calendar-plus-o',
            'label': _('Subscribe to Other Calendar'),
            'url': eventreverse(
                organizer,
                'presale:organizer.export',
                kwargs={'export_target': 'webcal'},
            )
            + webcal_suffix,
        },
        {
            'icon': 'fa-calendar',
            'label': _('iCal (full event)'),
            'url': ical_path,
        },
        {
            'icon': 'fa-code',
            'label': _('JSON (frab compatible)'),
            'url': export_url('schedule.json'),
        },
        {
            'icon': 'fa-code',
            'label': _('XML (frab compatible)'),
            'url': export_url('schedule.xml'),
        },
        {
            'icon': 'fa-calendar',
            'label': _('XCal (frab compatible)'),
            'url': export_url('schedule.xcal'),
        },
    ]
