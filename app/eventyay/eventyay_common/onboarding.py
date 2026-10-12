"""Helpers for the common user dashboard (onboarding + organised events)."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from allauth.account.models import EmailAddress
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse
from django.utils.formats import date_format
from django.utils.timesince import timesince
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope, scopes_disabled

from eventyay.base.meetup import is_meetup_event
from eventyay.base.models import Event, Order, Submission, User
from eventyay.base.settings import is_event_series_creation_enabled, is_meetup_creation_enabled
from eventyay.eventyay_common.permissions import (
    user_has_talk_dashboard_access,
    user_has_ticket_dashboard_access,
    user_has_video_dashboard_access,
)
from eventyay.eventyay_common.utils import EventCreatedFor
from eventyay.helpers.daterange import daterange
from eventyay.multidomain.urlreverse import eventreverse


RECOMMENDED_EVENTS_LIMIT = 6
MANAGED_EVENTS_LIMIT = 8

TICKET_PERMISSION_DIALOG_ID = 'ticket-permission-dialog'
TALK_PERMISSION_DIALOG_ID = 'talk-permission-dialog'
VIDEO_PERMISSION_DIALOG_ID = 'video-permission-dialog'


def user_has_verified_email(user: User) -> bool:
    if not user.is_authenticated or not user.email:
        return False
    return EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()


def _event_schedule_url(event: Event) -> str:
    try:
        return eventreverse(event, 'agenda:schedule')
    except NoReverseMatch:
        return eventreverse(event, 'presale:event.index')


def user_has_orders(user: User) -> bool:
    if not user_has_verified_email(user):
        return False
    with scopes_disabled():
        return Order.objects.filter(email__iexact=user.email).exists()


def user_has_sessions_or_proposals(user: User) -> bool:
    if not user.email:
        return False
    with scopes_disabled():
        return Submission.objects.filter(speakers__email__iexact=user.email).exists()


def user_has_organised_events(user: User, request: HttpRequest | None = None) -> bool:
    with scopes_disabled():
        return user.get_events_with_any_permission(request).exists()


def user_needs_onboarding(user: User, request: HttpRequest | None = None) -> bool:
    """Return True when the user has no personal Eventyay activity yet."""
    if user_has_orders(user):
        return False
    if user_has_sessions_or_proposals(user):
        return False
    if user_has_organised_events(user, request):
        return False
    return True


def get_missing_profile_fields(user: User) -> list[str]:
    """Return human-readable account fields that are still missing."""
    missing: list[str] = []
    if not (user.fullname or '').strip():
        missing.append(str(_('full name')))
    if not user.has_profile_picture:
        missing.append(str(_('profile picture')))
    return missing


def format_profile_incomplete_message(missing: list[str]) -> str:
    """Build a short prompt that names only the missing profile fields."""
    if not missing:
        return ''
    if len(missing) == 1:
        return str(_('Add your %(item)s to finish your profile.') % {'item': missing[0]})
    if len(missing) == 2:
        return str(
            _('Add your %(first)s and %(second)s to finish your profile.') % {'first': missing[0], 'second': missing[1]}
        )
    *head, last = missing
    return str(_('Add your %(items)s, and %(last)s to finish your profile.') % {'items': ', '.join(head), 'last': last})


def is_profile_incomplete(user: User) -> bool:
    """Account profile is incomplete without a display name or photo."""
    return bool(get_missing_profile_fields(user))


def build_profile_prompt_context(user: User) -> dict[str, Any]:
    missing = get_missing_profile_fields(user)
    return {
        'profile_incomplete': bool(missing),
        'profile_incomplete_message': format_profile_incomplete_message(missing),
        'edit_profile_url': reverse('eventyay_common:account.general'),
    }


def _public_upcoming_events_qs():
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    return Event.exclude_talks_testmode(
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects', 'cfp')
        .filter(live=True, is_public=True, testmode=False)
        .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
        .filter(Q(date_to__gte=today) | Q(date_to__isnull=True, date_from__gte=today))
    ).order_by('-startpage_featured', 'date_from')


def _event_date_range(event: Event) -> str:
    tzname = event.settings.get('timezone') or event.timezone or 'UTC'
    tz = ZoneInfo(str(tzname))
    if event.has_subevents:
        return str(_('Event series'))
    if event.date_to:
        return daterange(event.date_from.astimezone(tz), event.date_to.astimezone(tz))
    return event.get_date_range_display()


def _event_time_label(event: Event) -> str:
    if event.has_subevents:
        return str(_('Event series'))
    tzname = event.settings.get('timezone') or event.timezone or 'UTC'
    tz = ZoneInfo(str(tzname))
    if not event.date_from:
        return ''
    return date_format(event.date_from.astimezone(tz), 'TIME_FORMAT')


def _event_location_label(event: Event) -> str:
    location = str(event.location or '').strip()
    if location:
        return location.splitlines()[0]
    tzname = event.settings.get('timezone') or event.timezone
    if tzname:
        return str(tzname)
    return ''


def _event_cfp_is_open(event: Event) -> bool:
    from eventyay.base.models.cfp import CfP

    try:
        with scope(event=event):
            cfp = event.cfp
            return bool(cfp.is_open)
    except CfP.DoesNotExist:
        return False


def _event_kind(event: Event) -> dict[str, str]:
    """Return a short type label for cards: event, series, or meetup."""
    if is_meetup_event(event):
        return {
            'kind': 'meetup',
            'label': str(_('Meetup')),
            'tone': 'success',
            'icon': 'users',
        }
    if event.has_subevents:
        return {
            'kind': 'series',
            'label': str(_('Series')),
            'tone': 'warning',
            'icon': 'calendar',
        }
    return {
        'kind': 'event',
        'label': str(_('Event')),
        'tone': 'primary',
        'icon': 'ticket',
    }


def _event_badges(event: Event) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if event.presale_is_running:
        badges.append({'label': str(_('Tickets on sale')), 'tone': 'success'})
    if _event_cfp_is_open(event):
        badges.append({'label': str(_('Call for proposals')), 'tone': 'accent'})
    return badges


def _event_primary_action(event: Event) -> dict[str, str]:
    url = eventreverse(event, 'presale:event.index')
    cfp_open = _event_cfp_is_open(event)
    if cfp_open and not event.presale_is_running:
        return {'label': str(_('Submit proposal')), 'url': url}
    if event.presale_is_running:
        return {'label': str(_('Register')), 'url': url}
    return {'label': str(_('View event')), 'url': url}


def _base_event_card(event: Event) -> dict[str, Any]:
    return {
        'name': str(event.name),
        'image_url': event.preview_image_url_with_fallback or '',
        'date_range': _event_date_range(event),
        'time_label': _event_time_label(event),
        'location': _event_location_label(event),
        'kind': _event_kind(event),
        'badges': _event_badges(event),
        'organizer_name': str(event.organizer.name) if event.organizer_id else '',
    }


def build_recommended_event_cards(limit: int = RECOMMENDED_EVENTS_LIMIT) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    with scopes_disabled():
        events = list(_public_upcoming_events_qs()[:limit])
    for event in events:
        if event.has_component_testmode:
            continue
        with scope(event=event):
            card = _base_event_card(event)
            card['url'] = eventreverse(event, 'presale:event.index')
            card['primary_action'] = _event_primary_action(event)
            cards.append(card)
    return cards


def _module_action(
    *,
    label: str,
    icon: str,
    url: str | None = None,
    dialog_id: str | None = None,
    modal_target: str | None = None,
) -> dict[str, Any]:
    return {
        'label': label,
        'icon': icon,
        'url': url or '#',
        'dialog_id': dialog_id,
        'modal_target': modal_target,
    }


def _ticket_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if user_has_ticket_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Tickets')),
            icon='ticket',
            url=reverse(
                'control:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            ),
        )
    return _module_action(
        label=str(_('Tickets')),
        icon='ticket',
        dialog_id=TICKET_PERMISSION_DIALOG_ID,
    )


def _talk_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if event.settings.create_for != EventCreatedFor.BOTH.value and event.settings.talk_schedule_public is None:
        return _module_action(
            label=str(_('Talks')),
            icon='microphone',
            modal_target='#alert-modal',
        )
    if not user_has_talk_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Talks')),
            icon='microphone',
            dialog_id=TALK_PERMISSION_DIALOG_ID,
        )
    return _module_action(
        label=str(_('Talks')),
        icon='microphone',
        url=reverse('orga:event.dashboard', kwargs={'organizer': event.organizer.slug, 'event': event.slug}),
    )


def _video_module_action(event: Event, request: HttpRequest) -> dict[str, Any]:
    if user_has_video_dashboard_access(request.user, event.organizer, event, request=request):
        return _module_action(
            label=str(_('Video')),
            icon='video-camera',
            url=reverse(
                'eventyay_common:event.create_access_to_video',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            ),
        )
    return _module_action(
        label=str(_('Video')),
        icon='video-camera',
        dialog_id=VIDEO_PERMISSION_DIALOG_ID,
    )


def build_managed_event_card(event: Event, request: HttpRequest) -> dict[str, Any]:
    with scope(event=event):
        card = _base_event_card(event)
        card['url'] = reverse(
            'eventyay_common:event.index',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        card['module_actions'] = [
            _ticket_module_action(event, request),
            _talk_module_action(event, request),
            _video_module_action(event, request),
        ]
    return card


def build_managed_event_cards(
    request: HttpRequest, qs: QuerySet[Event], limit: int = MANAGED_EVENTS_LIMIT
) -> list[dict[str, Any]]:
    events = list(qs.prefetch_related('_settings_objects', 'cfp').select_related('organizer')[:limit])
    return [build_managed_event_card(event, request) for event in events]


def build_create_actions(request: HttpRequest) -> list[dict[str, Any]]:
    if not request.user.teams.filter(can_create_events=True).exists():
        return []
    actions = [
        {
            'title': str(_('Create event')),
            'description': str(_('Set up tickets, talks, and video for a new event.')),
            'url': reverse('eventyay_common:events.add'),
            'icon': 'plus-circle',
            'tone': 'primary',
        }
    ]
    if is_event_series_creation_enabled(request):
        actions.append(
            {
                'title': str(_('Create event series')),
                'description': str(_('Launch a multi-date series with shared settings.')),
                'url': reverse('eventyay_common:events.add') + '?series=1',
                'icon': 'calendar',
                'tone': 'accent',
            }
        )
    if is_meetup_creation_enabled(request):
        actions.append(
            {
                'title': str(_('Create meetup')),
                'description': str(_('Start a lightweight meetup with a simpler setup.')),
                'url': reverse('eventyay_common:events.add') + '?meetup=1',
                'icon': 'users',
                'tone': 'success',
            }
        )
    return actions


def build_onboarding_context(request: HttpRequest) -> dict[str, Any]:
    user = request.user
    can_create_event = user.teams.filter(can_create_events=True).exists()
    return {
        'is_onboarding_dashboard': True,
        'can_create_event': can_create_event,
        **build_profile_prompt_context(user),
        'recommended_events': build_recommended_event_cards(),
        'browse_events_url': reverse('presale:index'),
        'upcoming_events_url': reverse('presale:events.upcoming'),
        'open_calls_url': reverse('presale:events.upcoming') + '?cfp=open',
        'create_event_url': reverse('eventyay_common:events.add'),
        'search_events_url': reverse('presale:index'),
    }


def build_organiser_dashboard_context(request: HttpRequest, annotated_qs_factory) -> dict[str, Any]:
    """Build context for the organised-events dashboard.

    ``annotated_qs_factory`` is ``annotated_event_query`` from dashboards.py to
    avoid a circular import.
    """
    upcoming_qs = (
        annotated_qs_factory(request, lazy=False)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
        )
        .order_by('date_from', 'order_to', 'pk')
    )
    past_qs = (
        annotated_qs_factory(request, lazy=False)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        )
        .order_by('-order_to', 'pk')
    )
    series_qs = annotated_qs_factory(request, lazy=False).filter(has_subevents=True).order_by('-order_to', 'pk')

    can_create_event = request.user.teams.filter(can_create_events=True).exists()
    return {
        'is_onboarding_dashboard': False,
        'can_create_event': can_create_event,
        'create_actions': build_create_actions(request),
        'upcoming_events': build_managed_event_cards(request, upcoming_qs, limit=7),
        'past_events': build_managed_event_cards(request, past_qs, limit=8),
        'series_events': build_managed_event_cards(request, series_qs, limit=8),
        'events_list_url': reverse('eventyay_common:events'),
        'upcoming_list_url': reverse('eventyay_common:events') + '?ordering=date_from&status=date_future',
        'past_list_url': reverse('eventyay_common:events') + '?ordering=date_from&status=-date_to',
        'series_list_url': reverse('eventyay_common:events') + '?ordering=-date_to&status=series',
        **build_profile_prompt_context(request.user),
        'browse_events_url': reverse('presale:index'),
    }


def build_attention_items(request: HttpRequest) -> list[dict[str, Any]]:
    user = request.user
    if not user.is_authenticated:
        return []

    items: list[dict[str, Any]] = []

    if user_has_verified_email(user):
        with scopes_disabled():
            pending_orders = list(
                Order.objects.filter(
                    email__iexact=user.email,
                    status=Order.STATUS_PENDING,
                    require_approval=False,
                ).select_related('event', 'event__organizer')[:5]
            )
        for order in pending_orders:
            with scope(event=order.event):
                order_url = eventreverse(
                    order.event,
                    'presale:event.order',
                    kwargs={'order': order.code, 'secret': order.secret},
                )
            items.append(
                {
                    'title': str(_('Payment pending')),
                    'event_name': str(order.event.name),
                    'description': str(_('Order %(code)s requires payment.') % {'code': order.code}),
                    'action_label': str(_('Pay now')),
                    'url': order_url,
                    'tone': 'warning',
                    'icon': 'credit-card',
                }
            )

    if user_has_verified_email(user):
        with scopes_disabled():
            approval_orders = list(
                Order.objects.filter(
                    email__iexact=user.email,
                    status=Order.STATUS_PENDING,
                    require_approval=True,
                ).select_related('event', 'event__organizer')[:5]
            )
        for order in approval_orders:
            with scope(event=order.event):
                order_url = eventreverse(
                    order.event,
                    'presale:event.order',
                    kwargs={'order': order.code, 'secret': order.secret},
                )
            items.append(
                {
                    'title': str(_('Ticket approval needed')),
                    'event_name': str(order.event.name),
                    'description': str(_('Order %(code)s is awaiting organizer approval.') % {'code': order.code}),
                    'action_label': str(_('View order')),
                    'url': order_url,
                    'tone': 'info',
                    'icon': 'hourglass-half',
                }
            )

    if user.email:
        with scopes_disabled():
            unconfirmed_submissions = list(
                Submission.objects.filter(
                    speakers__email__iexact=user.email,
                    state='accepted',
                ).select_related('event', 'event__organizer')[:5]
            )
        for sub in unconfirmed_submissions:
            sub_url = reverse(
                'cfp:event.user.submission.edit',
                kwargs={'organizer': sub.event.organizer.slug, 'event': sub.event.slug, 'code': sub.code},
            )
            items.append(
                {
                    'title': str(_('Session confirmation required')),
                    'event_name': str(sub.event.name),
                    'description': str(
                        _('Your proposal "%(title)s" has been accepted! Please confirm your attendance.')
                        % {'title': sub.title}
                    ),
                    'action_label': str(_('Confirm session')),
                    'url': sub_url,
                    'tone': 'warning',
                    'icon': 'check-circle-o',
                }
            )

    if is_profile_incomplete(user):
        with scopes_disabled():
            has_speaker_activity = bool(
                user.email and Submission.objects.filter(speakers__email__iexact=user.email).exists()
            )
        title = _('Speaker profile incomplete') if has_speaker_activity else _('Profile incomplete')
        items.append(
            {
                'title': str(title),
                'event_name': '',
                'description': format_profile_incomplete_message(get_missing_profile_fields(user)),
                'action_label': str(_('Edit profile')),
                'url': reverse('eventyay_common:account.general'),
                'tone': 'info',
                'icon': 'user',
            }
        )

    with scopes_disabled():
        managed_events = user.get_events_with_permission('can_view_orders', request)
        if managed_events.exists():
            orders_needing_review = (
                Order.objects.filter(
                    event__in=managed_events,
                    status=Order.STATUS_PENDING,
                    require_approval=True,
                )
                .values('event__slug', 'event__organizer__slug', 'event__name')
                .annotate(cnt=Count('id'))[:5]
            )
            for item in orders_needing_review:
                rev_url = (
                    reverse(
                        'control:event.orders',
                        kwargs={'organizer': item['event__organizer__slug'], 'event': item['event__slug']},
                    )
                    + '?status=pa'
                )
                items.append(
                    {
                        'title': str(_('Orders needing approval')),
                        'event_name': str(item['event__name']),
                        'description': str(_('%(count)d order(s) waiting for approval.') % {'count': item['cnt']}),
                        'action_label': str(_('Review orders')),
                        'url': rev_url,
                        'tone': 'warning',
                        'icon': 'check-square-o',
                    }
                )

    return items


def build_next_up_card(request: HttpRequest) -> dict[str, Any] | None:
    user = request.user
    if not user.is_authenticated:
        return None

    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    candidates = []
    upcoming_event_filter = Q(date_to__gte=today) | Q(date_to__isnull=True, date_from__gte=today)
    upcoming_rel_filter = Q(event__date_to__gte=today) | Q(event__date_to__isnull=True, event__date_from__gte=today)

    if user_has_verified_email(user):
        with scopes_disabled():
            attendee_order = (
                Order.objects.filter(
                    email__iexact=user.email,
                )
                .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                .filter(upcoming_rel_filter)
                .select_related('event', 'event__organizer')
                .prefetch_related('event___settings_objects')
                .order_by('event__date_from')
                .first()
            )
            if attendee_order:
                candidates.append(
                    {
                        'event': attendee_order.event,
                        'role': 'attendee',
                        'order': attendee_order,
                        'date_from': attendee_order.event.date_from or today,
                    }
                )

    if user.email:
        with scopes_disabled():
            speaker_sub = (
                Submission.objects.filter(
                    speakers__email__iexact=user.email,
                    state__in=['confirmed', 'accepted'],
                )
                .filter(upcoming_rel_filter)
                .select_related('event', 'event__organizer')
                .prefetch_related('event___settings_objects')
                .order_by('event__date_from')
                .first()
            )
            if speaker_sub:
                candidates.append(
                    {
                        'event': speaker_sub.event,
                        'role': 'speaker',
                        'submission': speaker_sub,
                        'date_from': speaker_sub.event.date_from or today,
                    }
                )

    with scopes_disabled():
        managed = (
            user.get_events_with_any_permission(request)
            .filter(upcoming_event_filter)
            .select_related('organizer')
            .prefetch_related('_settings_objects')
            .order_by('date_from')
            .first()
        )
        if managed:
            candidates.append(
                {
                    'event': managed,
                    'role': 'organiser',
                    'date_from': managed.date_from or today,
                }
            )

    if not candidates:
        fallback_candidates = []
        if user_has_verified_email(user):
            with scopes_disabled():
                past_order = (
                    Order.objects.filter(
                        email__iexact=user.email,
                    )
                    .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                    .select_related('event', 'event__organizer')
                    .prefetch_related('event___settings_objects')
                    .order_by('-event__date_from')
                    .first()
                )
                if past_order:
                    fallback_candidates.append(
                        {
                            'event': past_order.event,
                            'role': 'attendee',
                            'order': past_order,
                            'date_from': past_order.event.date_from or today,
                        }
                    )
        if user.email:
            with scopes_disabled():
                past_sub = (
                    Submission.objects.filter(
                        speakers__email__iexact=user.email,
                        state__in=['confirmed', 'accepted'],
                    )
                    .select_related('event', 'event__organizer')
                    .prefetch_related('event___settings_objects')
                    .order_by('-event__date_from')
                    .first()
                )
                if past_sub:
                    fallback_candidates.append(
                        {
                            'event': past_sub.event,
                            'role': 'speaker',
                            'submission': past_sub,
                            'date_from': past_sub.event.date_from or today,
                        }
                    )
        with scopes_disabled():
            past_managed = (
                user.get_events_with_any_permission(request)
                .select_related('organizer')
                .prefetch_related('_settings_objects')
                .order_by('-date_from')
                .first()
            )
            if past_managed:
                fallback_candidates.append(
                    {
                        'event': past_managed,
                        'role': 'organiser',
                        'date_from': past_managed.date_from or today,
                    }
                )

        if fallback_candidates:
            fallback_candidates.sort(key=lambda c: c['date_from'], reverse=True)
            candidates.append(fallback_candidates[0])

    if not candidates:
        return None

    candidates.sort(key=lambda c: c['date_from'])
    top = candidates[0]
    ev = top['event']
    role = top['role']

    with scope(event=ev):
        card = _base_event_card(ev)
        card['role'] = role

        if role == 'organiser':
            card['role_label'] = str(_('Organiser'))
            card['status_label'] = str(_('Event live')) if ev.live else str(_('Draft'))
            card['status_tone'] = 'success' if ev.live else 'secondary'
            card['primary_action'] = {
                'label': str(_('Open dashboard')),
                'url': reverse(
                    'eventyay_common:event.index', kwargs={'organizer': ev.organizer.slug, 'event': ev.slug}
                ),
            }
            sec_links = []
            if user_has_ticket_dashboard_access(user, ev.organizer, ev, request=request):
                sec_links.append(
                    {
                        'label': str(_('Tickets')),
                        'url': reverse(
                            'control:event.index',
                            kwargs={'organizer': ev.organizer.slug, 'event': ev.slug},
                        ),
                    }
                )
            if user.has_event_permission(ev.organizer, ev, 'can_change_event_settings', request=request):
                sec_links.append(
                    {
                        'label': str(_('Settings')),
                        'url': reverse(
                            'eventyay_common:event.update', kwargs={'organizer': ev.organizer.slug, 'event': ev.slug}
                        ),
                    }
                )
            card['secondary_links'] = sec_links
        elif role == 'speaker':
            sub = top['submission']
            card['role_label'] = str(_('Speaker'))
            card['status_label'] = sub.get_state_display()
            card['status_tone'] = 'success' if sub.state == 'confirmed' else 'warning'
            card['primary_action'] = {
                'label': str(_('My session')),
                'url': reverse(
                    'cfp:event.user.submission.edit',
                    kwargs={'organizer': ev.organizer.slug, 'event': ev.slug, 'code': sub.code},
                ),
            }
            card['secondary_links'] = [
                {'label': str(_('Schedule')), 'url': _event_schedule_url(ev)},
                {'label': str(_('Details')), 'url': eventreverse(ev, 'presale:event.index')},
            ]
        else:
            ord = top['order']
            card['role_label'] = str(_('Attendee'))
            card['status_label'] = (
                str(_('Ticket confirmed')) if ord.status == Order.STATUS_PAID else ord.get_status_display()
            )
            card['status_tone'] = 'success' if ord.status == Order.STATUS_PAID else 'warning'
            card['primary_action'] = {
                'label': str(_('View ticket')),
                'url': eventreverse(ev, 'presale:event.order', kwargs={'order': ord.code, 'secret': ord.secret}),
            }
            card['secondary_links'] = [
                {'label': str(_('Schedule')), 'url': _event_schedule_url(ev)},
                {'label': str(_('Details')), 'url': eventreverse(ev, 'presale:event.index')},
            ]

    return card


def build_role_aware_event_cards(request: HttpRequest, limit: int = 8) -> list[dict[str, Any]]:
    user = request.user
    if not user.is_authenticated:
        return []

    events_dict: dict[int, dict[str, Any]] = {}
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    upcoming_event_filter = Q(date_to__gte=today) | Q(date_to__isnull=True, date_from__gte=today)
    upcoming_rel_filter = Q(event__date_to__gte=today) | Q(event__date_to__isnull=True, event__date_from__gte=today)

    with scopes_disabled():
        managed = list(
            user.get_events_with_any_permission(request)
            .filter(upcoming_event_filter)
            .select_related('organizer')
            .prefetch_related('_settings_objects', 'cfp')
            .order_by('date_from')[:limit]
        )
        for ev in managed:
            events_dict[ev.pk] = {
                'event': ev,
                'is_organiser': True,
                'is_speaker': False,
                'is_attendee': False,
            }

    if user.email:
        with scopes_disabled():
            sub_event_ids = list(
                Submission.objects.filter(speakers__email__iexact=user.email)
                .filter(upcoming_rel_filter)
                .order_by('event__date_from')
                .values_list('event_id', flat=True)
                .distinct()[:limit]
            )
            if sub_event_ids:
                subs = list(
                    Submission.objects.filter(speakers__email__iexact=user.email, event_id__in=sub_event_ids)
                    .select_related('event', 'event__organizer')
                    .prefetch_related('event___settings_objects', 'event__cfp')
                )
                for sub in subs:
                    ev = sub.event
                    if ev.pk not in events_dict:
                        events_dict[ev.pk] = {
                            'event': ev,
                            'is_organiser': False,
                            'is_speaker': True,
                            'is_attendee': False,
                            'submission': sub,
                        }
                    else:
                        events_dict[ev.pk]['is_speaker'] = True
                        if 'submission' not in events_dict[ev.pk]:
                            events_dict[ev.pk]['submission'] = sub

    if user_has_verified_email(user):
        with scopes_disabled():
            order_event_ids = list(
                Order.objects.filter(email__iexact=user.email)
                .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                .filter(upcoming_rel_filter)
                .order_by('event__date_from')
                .values_list('event_id', flat=True)
                .distinct()[:limit]
            )
            if order_event_ids:
                orders = list(
                    Order.objects.filter(email__iexact=user.email, event_id__in=order_event_ids)
                    .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                    .select_related('event', 'event__organizer')
                    .prefetch_related('event___settings_objects', 'event__cfp')
                )
                for ord in orders:
                    ev = ord.event
                    if ev.pk not in events_dict:
                        events_dict[ev.pk] = {
                            'event': ev,
                            'is_organiser': False,
                            'is_speaker': False,
                            'is_attendee': True,
                            'order': ord,
                        }
                    else:
                        events_dict[ev.pk]['is_attendee'] = True
                        if 'order' not in events_dict[ev.pk]:
                            events_dict[ev.pk]['order'] = ord

    if not events_dict:
        with scopes_disabled():
            managed_past = list(
                user.get_events_with_any_permission(request)
                .filter(~upcoming_event_filter)
                .select_related('organizer')
                .prefetch_related('_settings_objects', 'cfp')
                .order_by('-date_from')[:limit]
            )
            for ev in managed_past:
                events_dict[ev.pk] = {
                    'event': ev,
                    'is_organiser': True,
                    'is_speaker': False,
                    'is_attendee': False,
                }

        if user.email:
            with scopes_disabled():
                past_sub_event_ids = list(
                    Submission.objects.filter(speakers__email__iexact=user.email)
                    .filter(~upcoming_rel_filter)
                    .order_by('-event__date_from')
                    .values_list('event_id', flat=True)
                    .distinct()[:limit]
                )
                if past_sub_event_ids:
                    subs_past = list(
                        Submission.objects.filter(speakers__email__iexact=user.email, event_id__in=past_sub_event_ids)
                        .select_related('event', 'event__organizer')
                        .prefetch_related('event___settings_objects', 'event__cfp')
                    )
                    for sub in subs_past:
                        ev = sub.event
                        if ev.pk not in events_dict:
                            events_dict[ev.pk] = {
                                'event': ev,
                                'is_organiser': False,
                                'is_speaker': True,
                                'is_attendee': False,
                                'submission': sub,
                            }
                        else:
                            events_dict[ev.pk]['is_speaker'] = True
                            if 'submission' not in events_dict[ev.pk]:
                                events_dict[ev.pk]['submission'] = sub

        if user_has_verified_email(user):
            with scopes_disabled():
                past_order_event_ids = list(
                    Order.objects.filter(email__iexact=user.email)
                    .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                    .filter(~upcoming_rel_filter)
                    .order_by('-event__date_from')
                    .values_list('event_id', flat=True)
                    .distinct()[:limit]
                )
                if past_order_event_ids:
                    orders_past = list(
                        Order.objects.filter(email__iexact=user.email, event_id__in=past_order_event_ids)
                        .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
                        .select_related('event', 'event__organizer')
                        .prefetch_related('event___settings_objects', 'event__cfp')
                    )
                    for ord in orders_past:
                        ev = ord.event
                        if ev.pk not in events_dict:
                            events_dict[ev.pk] = {
                                'event': ev,
                                'is_organiser': False,
                                'is_speaker': False,
                                'is_attendee': True,
                                'order': ord,
                            }
                        else:
                            events_dict[ev.pk]['is_attendee'] = True
                            if 'order' not in events_dict[ev.pk]:
                                events_dict[ev.pk]['order'] = ord

    all_items = list(events_dict.values())
    upcoming_items = [
        x
        for x in all_items
        if (x['event'].date_to and x['event'].date_to >= today)
        or (x['event'].date_from and x['event'].date_from >= today)
    ]
    past_items = [x for x in all_items if x not in upcoming_items]
    upcoming_items.sort(key=lambda x: x['event'].date_from.timestamp() if x['event'].date_from else 0)
    past_items.sort(key=lambda x: -(x['event'].date_from.timestamp() if x['event'].date_from else 0))
    target_items = upcoming_items if upcoming_items else past_items

    cards = []
    for item in target_items[:limit]:
        ev = item['event']
        with scope(event=ev):
            card = _base_event_card(ev)
            card['url'] = (
                reverse('eventyay_common:event.index', kwargs={'organizer': ev.organizer.slug, 'event': ev.slug})
                if item['is_organiser']
                else eventreverse(ev, 'presale:event.index')
            )

            role_badges = []
            if item['is_organiser']:
                role_badges.append({'label': str(_('Organiser')), 'tone': 'primary'})
            if item['is_speaker']:
                role_badges.append({'label': str(_('Speaker')), 'tone': 'info'})
            if item['is_attendee']:
                role_badges.append({'label': str(_('Attendee')), 'tone': 'success'})
            card['role_badges'] = role_badges

            if item['is_organiser']:
                status_label = str(_('Event live')) if ev.live else str(_('Draft'))
                card['status_badge'] = {'label': status_label, 'tone': 'success' if ev.live else 'secondary'}
                card['module_actions'] = [
                    _ticket_module_action(ev, request),
                    _talk_module_action(ev, request),
                    _video_module_action(ev, request),
                ]
            elif item['is_speaker']:
                sub = item['submission']
                card['status_badge'] = {
                    'label': sub.get_state_display(),
                    'tone': 'success' if sub.state == 'confirmed' else 'warning',
                }
                card['primary_action'] = {
                    'label': str(_('My session')),
                    'url': reverse(
                        'cfp:event.user.submission.edit',
                        kwargs={'organizer': ev.organizer.slug, 'event': ev.slug, 'code': sub.code},
                    ),
                }
                card['secondary_links'] = [
                    {'label': str(_('Schedule')), 'url': _event_schedule_url(ev)},
                    {'label': str(_('Details')), 'url': eventreverse(ev, 'presale:event.index')},
                ]
            else:
                ord = item['order']
                status_label = (
                    str(_('Ticket confirmed')) if ord.status == Order.STATUS_PAID else ord.get_status_display()
                )
                card['status_badge'] = {
                    'label': status_label,
                    'tone': 'success' if ord.status == Order.STATUS_PAID else 'warning',
                }
                card['primary_action'] = {
                    'label': str(_('View ticket')),
                    'url': eventreverse(ev, 'presale:event.order', kwargs={'order': ord.code, 'secret': ord.secret}),
                }
                card['secondary_links'] = [
                    {'label': str(_('Schedule')), 'url': _event_schedule_url(ev)},
                    {'label': str(_('Details')), 'url': eventreverse(ev, 'presale:event.index')},
                ]

            cards.append(card)

    return cards


def build_user_tickets(request: HttpRequest, limit: int = 5) -> list[dict[str, Any]]:
    user = request.user
    if not user_has_verified_email(user):
        return []
    with scopes_disabled():
        orders = list(
            Order.objects.filter(email__iexact=user.email)
            .exclude(status__in=[Order.STATUS_CANCELED, Order.STATUS_EXPIRED])
            .select_related('event', 'event__organizer')
            .order_by('-datetime')[:limit]
        )
    cards = []
    for order in orders:
        with scope(event=order.event):
            order_url = eventreverse(
                order.event,
                'presale:event.order',
                kwargs={'order': order.code, 'secret': order.secret},
            )
            date_range = _event_date_range(order.event)
            status_label = order.get_status_display()
            status_tone = (
                'success'
                if order.status == Order.STATUS_PAID
                else ('warning' if order.status == Order.STATUS_PENDING else 'secondary')
            )
            if order.status == Order.STATUS_PENDING and order.require_approval:
                status_label = str(_('Approval pending'))
                status_tone = 'info'
            cards.append(
                {
                    'code': order.code,
                    'event_name': str(order.event.name),
                    'date_range': date_range,
                    'status': status_label,
                    'status_tone': status_tone,
                    'url': order_url,
                    'action_label': str(_('Pay now'))
                    if order.status == Order.STATUS_PENDING and not order.require_approval
                    else str(_('View ticket')),
                }
            )
    return cards


def build_user_sessions(request: HttpRequest, limit: int = 5) -> list[dict[str, Any]]:
    user = request.user
    if not user.is_authenticated or not user.email:
        return []
    with scopes_disabled():
        submissions = list(
            Submission.objects.filter(speakers__email__iexact=user.email)
            .select_related('event', 'event__organizer')
            .order_by('-event__date_from', '-id')[:limit]
        )
    cards = []
    for sub in submissions:
        sub_url = reverse(
            'cfp:event.user.submission.edit',
            kwargs={'organizer': sub.event.organizer.slug, 'event': sub.event.slug, 'code': sub.code},
        )
        tone = (
            'success'
            if sub.state in ('accepted', 'confirmed')
            else ('warning' if sub.state == 'submitted' else 'secondary')
        )
        cards.append(
            {
                'title': sub.title,
                'event_name': str(sub.event.name),
                'date_range': _event_date_range(sub.event),
                'status': sub.get_state_display(),
                'status_tone': tone,
                'url': sub_url,
                'action_label': str(_('View session'))
                if sub.state in ('accepted', 'confirmed')
                else str(_('View proposal')),
            }
        )
    return cards


def build_organising_events(request: HttpRequest, limit: int = 5) -> list[dict[str, Any]]:
    user = request.user
    if not user.is_authenticated:
        return []
    with scopes_disabled():
        events = list(
            user.get_events_with_any_permission(request)
            .select_related('organizer')
            .order_by('-date_from', 'name')[:limit]
        )
    cards = []
    for event in events:
        dashboard_url = reverse(
            'eventyay_common:event.index',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        status_label = str(_('Event live')) if event.live else str(_('Draft'))
        cards.append(
            {
                'name': str(event.name),
                'date_range': _event_date_range(event),
                'status': status_label,
                'status_tone': 'success' if event.live else 'secondary',
                'role': str(_('Organiser')),
                'url': dashboard_url,
                'action_label': str(_('Open dashboard')),
            }
        )
    return cards


def build_recent_activity(request: HttpRequest, limit: int = 5) -> list[dict[str, Any]]:
    user = request.user
    if not user.is_authenticated:
        return []
    items: list[dict[str, Any]] = []

    if user_has_verified_email(user):
        with scopes_disabled():
            orders = list(
                Order.objects.filter(email__iexact=user.email).select_related('event').order_by('-datetime')[:3]
            )
            for order in orders:
                with scope(event=order.event):
                    order_url = eventreverse(
                        order.event,
                        'presale:event.order',
                        kwargs={'order': order.code, 'secret': order.secret},
                    )
                items.append(
                    {
                        'timestamp': order.datetime,
                        'time_ago': timesince(order.datetime),
                        'icon': 'ticket',
                        'title': str(
                            _('Order %(code)s (%(status)s)')
                            % {'code': order.code, 'status': order.get_status_display()}
                        ),
                        'event_name': str(order.event.name),
                        'url': order_url,
                    }
                )

    if user.email:
        with scopes_disabled():
            submissions = list(
                Submission.objects.filter(speakers__email__iexact=user.email)
                .select_related('event', 'event__organizer')
                .order_by('-id')[:3]
            )
            for sub in submissions:
                created = getattr(sub, 'created', None)
                items.append(
                    {
                        'timestamp': created or now(),
                        'time_ago': timesince(created) if created else '',
                        'icon': 'microphone',
                        'title': str(
                            _('Session "%(title)s" (%(status)s)')
                            % {'title': sub.title, 'status': sub.get_state_display()}
                        ),
                        'event_name': str(sub.event.name),
                        'url': reverse(
                            'cfp:event.user.submission.edit',
                            kwargs={'organizer': sub.event.organizer.slug, 'event': sub.event.slug, 'code': sub.code},
                        ),
                    }
                )

    items.sort(key=lambda x: x.get('timestamp') or now(), reverse=True)
    return items[:limit]


def build_role_aware_dashboard_context(request: HttpRequest, annotated_qs_factory=None) -> dict[str, Any]:
    user = request.user
    can_create_event = user.is_authenticated and user.teams.filter(can_create_events=True).exists()

    attention_items = build_attention_items(request)
    next_up = build_next_up_card(request)
    my_events = build_role_aware_event_cards(request)
    my_tickets = build_user_tickets(request)
    my_sessions = build_user_sessions(request)
    organising_events = build_organising_events(request)
    recent_activity = build_recent_activity(request)

    if annotated_qs_factory is not None:
        organiser_ctx = build_organiser_dashboard_context(request, annotated_qs_factory)
    else:
        organiser_ctx = {}

    return {
        **organiser_ctx,
        'is_onboarding_dashboard': False,
        'can_create_event': can_create_event,
        'create_event_url': reverse('eventyay_common:events.add'),
        'create_actions': build_create_actions(request),
        'search_events_url': reverse('presale:index'),
        'typeahead_source_url': reverse('control:events.typeahead'),
        'next_up': next_up,
        'attention_items': attention_items,
        'has_attention': bool(attention_items),
        'my_events': my_events,
        'has_my_events': bool(my_events),
        'events_list_url': reverse('eventyay_common:events'),
        'my_tickets': my_tickets,
        'has_tickets': bool(my_tickets),
        'tickets_list_url': reverse('eventyay_common:orders'),
        'my_sessions': my_sessions,
        'has_sessions': bool(my_sessions),
        'sessions_list_url': reverse('eventyay_common:sessions'),
        'organising_events': organising_events,
        'has_organising': bool(organising_events),
        'organising_list_url': reverse('eventyay_common:events'),
        'organizers_list_url': reverse('eventyay_common:organizers'),
        'recent_activity': recent_activity,
        'has_recent_activity': bool(recent_activity),
        'browse_events_url': reverse('presale:index'),
        **build_profile_prompt_context(user),
    }
