import hashlib
import json
import logging

from allauth.account.models import EmailAddress
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now as tz_now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from django_scopes import scopes_disabled

from eventyay.base.models import Event, LogEntry, Organizer, User
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailQueueFilter,
    AdminEmailQueueRecipient,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.base.models.mail import MailTemplate, MailTemplateRoles
from eventyay.base.models.orders import Order, OrderPosition
from eventyay.base.models.organizer import Team
from eventyay.base.models.submission import Submission
from eventyay.common.mail import mail_send_task
from eventyay.common.sanitizers import sanitize_email_html
from eventyay.control.forms.admin.admin_messages import (
    AdminComposeForm,
    AdminComposeRecipientsForm,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin, StaffMemberRequiredMixin
from eventyay.control.tasks import send_admin_email
from eventyay.control.views import PaginationMixin

logger = logging.getLogger(__name__)

HIGH_RECIPIENT_THRESHOLD = 500


def _audience_fingerprint(filters: dict, count: int = 0) -> str:
    payload = json.dumps({'filters': filters, 'count': count}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def resolve_admin_recipients(filters: dict) -> tuple[list[dict], int]:
    recipient_group = filters.get('recipient_group', AdminRecipientGroup.ALL_USERS)
    account_status = filters.get('account_status', '')
    user_role = filters.get('user_role', '')
    language = filters.get('language', '')
    event_status = filters.get('event_status', '')
    created_after = filters.get('created_after')
    created_before = filters.get('created_before')
    last_active_after = filters.get('last_active_after')
    last_active_before = filters.get('last_active_before')
    selected_organiser_ids = filters.get('selected_organisers', [])
    selected_event_ids = filters.get('selected_events', [])
    selected_user_ids = filters.get('selected_users', [])
    exclude_admins = filters.get('exclude_admins', False)
    exclude_inactive = filters.get('exclude_inactive', False)
    exclude_unconfirmed = filters.get('exclude_unconfirmed_email', False)
    event_date_from = filters.get('event_date_from')
    event_date_to = filters.get('event_date_to')
    organiser_status = filters.get('organiser_status', '')
    billing_status = filters.get('billing_status', '')
    ticketing_status = filters.get('ticketing_status', '')
    cfp_status = filters.get('cfp_status', '')
    setup_status = filters.get('setup_status', '')

    qs = User.objects.exclude(email__isnull=True).exclude(email='').exclude(deleted=True)

    if exclude_inactive:
        qs = qs.filter(is_active=True)
    if exclude_admins:
        qs = qs.filter(is_staff=False, is_administrator=False)

    if account_status == 'active':
        qs = qs.filter(is_active=True)
    elif account_status == 'banned':
        qs = qs.filter(moderation_state='banned')
    elif account_status == 'verified':
        verified_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=verified_ids)
    elif account_status == 'unverified':
        verified_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.exclude(pk__in=verified_ids)

    if user_role == 'admin':
        qs = qs.filter(Q(is_staff=True) | Q(is_administrator=True))
    elif user_role == 'staff':
        qs = qs.filter(is_staff=True)
    elif user_role == 'organiser':
        qs = qs.filter(teams__isnull=False).distinct()
    elif user_role == 'user':
        qs = qs.filter(teams__isnull=True, is_staff=False, is_administrator=False)

    if language:
        qs = qs.filter(locale=language)

    if created_after:
        qs = qs.filter(date_joined__gte=created_after)
    if created_before:
        qs = qs.filter(date_joined__lte=created_before)
    if last_active_after:
        qs = qs.filter(last_login__gte=last_active_after)
    if last_active_before:
        qs = qs.filter(last_login__lte=last_active_before)

    if exclude_unconfirmed:
        confirmed_ids = EmailAddress.objects.filter(
            verified=True, primary=True
        ).values_list('user_id', flat=True)
        qs = qs.filter(pk__in=confirmed_ids)

    extra_emails: set[str] = set()

    with scopes_disabled():
        if recipient_group == AdminRecipientGroup.ALL_USERS:
            pass

        elif recipient_group == AdminRecipientGroup.ALL_ORGANISERS:
            qs = qs.filter(teams__isnull=False).distinct()

        elif recipient_group == AdminRecipientGroup.EVENT_ORGANISERS:
            if selected_event_ids:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                ).distinct()
            elif selected_organiser_ids:
                qs = qs.filter(teams__organizer__pk__in=selected_organiser_ids).distinct()
            else:
                qs = qs.filter(teams__isnull=False).distinct()

        elif recipient_group == AdminRecipientGroup.EVENT_TEAM_MEMBERS:
            team_filter = Q(teams__isnull=False)
            if selected_event_ids:
                team_filter = Q(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                )
            elif selected_organiser_ids:
                team_filter = Q(teams__organizer__pk__in=selected_organiser_ids)
            qs = qs.filter(team_filter).distinct()

        elif recipient_group == AdminRecipientGroup.SPEAKERS:
            speaker_qs = Submission.objects.all()
            if selected_event_ids:
                speaker_qs = speaker_qs.filter(event__pk__in=selected_event_ids)
            speaker_user_ids = speaker_qs.values_list('speakers__pk', flat=True).distinct()
            qs = qs.filter(pk__in=speaker_user_ids)

        elif recipient_group == AdminRecipientGroup.REVIEWERS:
            qs = qs.filter(teams__is_reviewer=True).distinct()
            if selected_event_ids:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=selected_event_ids)
                    | Q(teams__limit_events__pk__in=selected_event_ids)
                ).distinct()

        elif recipient_group == AdminRecipientGroup.ATTENDEES:
            pos_qs = OrderPosition.objects.filter(
                attendee_email__isnull=False
            ).exclude(attendee_email='')
            if selected_event_ids:
                pos_qs = pos_qs.filter(order__event__pk__in=selected_event_ids)
            order_qs = Order.objects.filter(
                status__in=['p', 'n']
            ).exclude(email__isnull=True).exclude(email='')
            if selected_event_ids:
                order_qs = order_qs.filter(event__pk__in=selected_event_ids)
            qs = qs.filter(
                Q(email__in=pos_qs.values('attendee_email'))
                | Q(email__in=order_qs.values('email'))
            ).distinct()
            all_user_emails = set(qs.values_list('email', flat=True))
            all_attendee_emails = set(
                pos_qs.values_list('attendee_email', flat=True).distinct()
            ) | set(order_qs.values_list('email', flat=True).distinct())
            extra_emails = {e.strip().lower() for e in all_attendee_emails} - {e.lower() for e in all_user_emails}

        elif recipient_group == AdminRecipientGroup.SELECTED_USERS:
            if selected_user_ids:
                qs = qs.filter(pk__in=selected_user_ids)
            else:
                qs = qs.none()

    if event_status and recipient_group in (
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
        AdminRecipientGroup.SPEAKERS,
        AdminRecipientGroup.REVIEWERS,
        AdminRecipientGroup.ATTENDEES,
    ):
        n = tz_now()
        with scopes_disabled():
            if event_status == 'live':
                event_pks = list(Event.objects.filter(live=True).values_list('pk', flat=True))
            elif event_status == 'draft':
                event_pks = list(Event.objects.filter(live=False).values_list('pk', flat=True))
            elif event_status == 'past':
                event_pks = list(Event.objects.filter(
                    Q(date_to__lt=n) | Q(date_to__isnull=True, date_from__lt=n)
                ).values_list('pk', flat=True))
            else:
                event_pks = None

            if event_pks is not None:
                if recipient_group in (
                    AdminRecipientGroup.EVENT_ORGANISERS,
                    AdminRecipientGroup.EVENT_TEAM_MEMBERS,
                    AdminRecipientGroup.REVIEWERS,
                ):
                    qs = qs.filter(
                        Q(teams__all_events=True, teams__organizer__events__pk__in=event_pks)
                        | Q(teams__limit_events__pk__in=event_pks)
                    ).distinct()

                elif recipient_group == AdminRecipientGroup.SPEAKERS:
                    speaker_ids = Submission.objects.filter(
                        event__pk__in=event_pks
                    ).values_list('speakers__pk', flat=True).distinct()
                    qs = qs.filter(pk__in=speaker_ids)

                elif recipient_group == AdminRecipientGroup.ATTENDEES:
                    filtered_pos_qs = pos_qs.filter(order__event__pk__in=event_pks)
                    filtered_order_qs = order_qs.filter(event__pk__in=event_pks)
                    all_user_emails_evt = set(qs.values_list('email', flat=True))
                    all_event_emails = (
                        set(filtered_pos_qs.values_list('attendee_email', flat=True).distinct())
                        | set(filtered_order_qs.values_list('email', flat=True).distinct())
                    )
                    extra_emails = {e.strip().lower() for e in all_event_emails} - {
                        e.strip().lower() for e in all_user_emails_evt
                    }

    if (event_date_from or event_date_to) and recipient_group not in (
        AdminRecipientGroup.ALL_USERS,
        AdminRecipientGroup.SELECTED_USERS,
    ):
        with scopes_disabled():
            event_date_qs = Event.objects.all()
            if event_date_from:
                event_date_qs = event_date_qs.filter(date_from__date__gte=event_date_from)
            if event_date_to:
                event_date_qs = event_date_qs.filter(date_from__date__lte=event_date_to)
            date_event_pks = list(event_date_qs.values_list('pk', flat=True))
            qs = qs.filter(
                Q(teams__all_events=True, teams__organizer__events__pk__in=date_event_pks)
                | Q(teams__limit_events__pk__in=date_event_pks)
            ).distinct()

    if organiser_status and recipient_group in (
        AdminRecipientGroup.ALL_ORGANISERS,
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
    ):
        with scopes_disabled():
            n = tz_now()
            if organiser_status == 'has_active':
                active_org_ids = Event.objects.filter(live=True).values_list('organizer_id', flat=True).distinct()
                qs = qs.filter(teams__organizer__pk__in=active_org_ids).distinct()
            elif organiser_status == 'has_draft':
                draft_org_ids = Event.objects.filter(live=False).values_list('organizer_id', flat=True).distinct()
                qs = qs.filter(teams__organizer__pk__in=draft_org_ids).distinct()
            elif organiser_status == 'has_past':
                past_org_ids = Event.objects.filter(
                    Q(date_to__lt=n) | Q(date_to__isnull=True, date_from__lt=n)
                ).values_list('organizer_id', flat=True).distinct()
                qs = qs.filter(teams__organizer__pk__in=past_org_ids).distinct()
            elif organiser_status == 'no_events':
                org_with_events = Event.objects.values_list('organizer_id', flat=True).distinct()
                qs = qs.filter(teams__organizer__isnull=False).exclude(
                    teams__organizer__pk__in=org_with_events
                ).distinct()

    if billing_status and recipient_group in (
        AdminRecipientGroup.ALL_ORGANISERS,
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
    ):
        from eventyay.base.models.organizer import OrganizerBillingModel
        with scopes_disabled():
            if billing_status == 'configured':
                billed_org_ids = OrganizerBillingModel.objects.filter(
                    stripe_customer_id__isnull=False
                ).exclude(stripe_customer_id='').values_list('organizer_id', flat=True)
                qs = qs.filter(teams__organizer__pk__in=billed_org_ids).distinct()
            elif billing_status == 'missing':
                billed_org_ids = OrganizerBillingModel.objects.filter(
                    stripe_customer_id__isnull=False
                ).exclude(stripe_customer_id='').values_list('organizer_id', flat=True)
                qs = qs.filter(teams__organizer__isnull=False).exclude(
                    teams__organizer__pk__in=billed_org_ids
                ).distinct()

    # Ticketing status filter
    if ticketing_status and recipient_group in (
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
    ):
        with scopes_disabled():
            from eventyay.base.models.product import Product
            if ticketing_status == 'shop_enabled':
                shop_event_ids = Event.objects.filter(live=True).values_list('pk', flat=True)
            elif ticketing_status == 'shop_disabled':
                shop_event_ids = Event.objects.filter(live=False).values_list('pk', flat=True)
            elif ticketing_status == 'has_paid':
                shop_event_ids = Product.objects.filter(
                    free_price=False
                ).values_list('event_id', flat=True).distinct()
            elif ticketing_status == 'has_free':
                shop_event_ids = Product.objects.filter(
                    free_price=True
                ).values_list('event_id', flat=True).distinct()
            else:
                shop_event_ids = None
            if shop_event_ids is not None:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=shop_event_ids)
                    | Q(teams__limit_events__pk__in=shop_event_ids)
                ).distinct()

    if cfp_status and recipient_group in (
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
        AdminRecipientGroup.SPEAKERS,
        AdminRecipientGroup.REVIEWERS,
    ):
        from eventyay.base.models.cfp import CfP
        from eventyay.base.models.submission import Submission, SubmissionStates
        with scopes_disabled():
            if cfp_status == 'cfp_open':
                cfp_event_ids = CfP.objects.filter(
                    deadline__isnull=True
                ).values_list('event_id', flat=True).distinct() | CfP.objects.filter(
                    deadline__gte=tz_now()
                ).values_list('event_id', flat=True).distinct()
            elif cfp_status == 'cfp_closed':
                cfp_event_ids = CfP.objects.filter(
                    deadline__lt=tz_now()
                ).values_list('event_id', flat=True).distinct()
            elif cfp_status == 'has_pending':
                cfp_event_ids = Submission.objects.filter(
                    state=SubmissionStates.SUBMITTED
                ).values_list('event_id', flat=True).distinct()
            else:
                cfp_event_ids = None
            if cfp_event_ids is not None:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=cfp_event_ids)
                    | Q(teams__limit_events__pk__in=cfp_event_ids)
                ).distinct()

    if setup_status and recipient_group in (
        AdminRecipientGroup.EVENT_ORGANISERS,
        AdminRecipientGroup.EVENT_TEAM_MEMBERS,
    ):
        with scopes_disabled():
            from eventyay.base.models.product import Product, Question
            if setup_status == 'missing_ticket':
                events_with_tickets = Product.objects.values_list('event_id', flat=True).distinct()
                setup_event_ids = Event.objects.exclude(
                    pk__in=events_with_tickets
                ).values_list('pk', flat=True)
            elif setup_status == 'missing_payment':
                from eventyay.base.models.event import Event_SettingsStore
                events_with_payment = Event_SettingsStore.objects.filter(
                    key__in=['payment_stripe__publishable_key', 'payment_paypal__client_id']
                ).values_list('object_id', flat=True).distinct()
                setup_event_ids = Event.objects.exclude(
                    pk__in=events_with_payment
                ).values_list('pk', flat=True)
            elif setup_status == 'missing_schedule':
                from eventyay.base.models.submission import Submission
                events_with_schedule = Submission.objects.filter(
                    slot__isnull=False
                ).values_list('event_id', flat=True).distinct()
                setup_event_ids = Event.objects.exclude(
                    pk__in=events_with_schedule
                ).values_list('pk', flat=True)
            else:
                setup_event_ids = None
            if setup_event_ids is not None:
                qs = qs.filter(
                    Q(teams__all_events=True, teams__organizer__events__pk__in=setup_event_ids)
                    | Q(teams__limit_events__pk__in=setup_event_ids)
                ).distinct()

    seen: set[str] = set()
    result: list[dict] = []
    reason = str(dict(AdminRecipientGroup.choices).get(recipient_group, recipient_group))
    skipped = 0

    for user in qs.only('pk', 'email', 'fullname', 'is_active', 'is_staff', 'is_administrator'):
        raw_email = user.email or ''
        if not raw_email.strip():
            skipped += 1
            continue
        email_lower = raw_email.strip().lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)

        role = 'Admin' if (user.is_administrator or user.is_staff) else 'User'
        result.append({
            'user_id': user.pk,
            'email': user.email,
            'name': user.get_full_name() or user.email,
            'status': 'Active' if user.is_active else 'Inactive',
            'role': role,
            'reason': reason,
        })

    for email in extra_emails:
        if email not in seen:
            seen.add(email)
            result.append({
                'user_id': None,
                'email': email,
                'name': email,
                'status': '',
                'role': _('Attendee'),
                'reason': reason,
            })

    return result, skipped


def _extract_filter_dict(form_data: dict) -> dict:
    filters = {
        'recipient_group': form_data.get('recipient_group', AdminRecipientGroup.ALL_USERS),
        'account_status': form_data.get('account_status', ''),
        'user_role': form_data.get('user_role', ''),
        'language': form_data.get('language', ''),
        'event_status': form_data.get('event_status', ''),
        'event_date_from': form_data.get('event_date_from'),
        'event_date_to': form_data.get('event_date_to'),
        'organiser_status': form_data.get('organiser_status', ''),
        'billing_status': form_data.get('billing_status', ''),
        'ticketing_status': form_data.get('ticketing_status', ''),
        'cfp_status': form_data.get('cfp_status', ''),
        'setup_status': form_data.get('setup_status', ''),
        'created_after': form_data.get('created_after'),
        'created_before': form_data.get('created_before'),
        'last_active_after': form_data.get('last_active_after'),
        'last_active_before': form_data.get('last_active_before'),
        'exclude_admins': form_data.get('exclude_admins', False),
        'exclude_inactive': form_data.get('exclude_inactive', False),
        'exclude_unconfirmed_email': form_data.get('exclude_unconfirmed_email', False),
    }

    for key in ('selected_organisers', 'selected_events', 'selected_users'):
        val = form_data.get(key)
        if val:
            if hasattr(val, 'values_list'):
                filters[key] = list(val.values_list('pk', flat=True))
            else:
                filters[key] = [int(x) for x in str(val).split(',') if x.strip().isdigit()]
        else:
            filters[key] = []

    return filters


def _save_filters(mail: AdminEmailQueue, filters: dict) -> AdminEmailQueueFilter:
    obj, _created = AdminEmailQueueFilter.objects.update_or_create(
        mail=mail,
        defaults={
            'account_status': filters.get('account_status', ''),
            'user_role': filters.get('user_role', ''),
            'language': filters.get('language', ''),
            'created_after': filters.get('created_after'),
            'created_before': filters.get('created_before'),
            'last_active_after': filters.get('last_active_after'),
            'last_active_before': filters.get('last_active_before'),
            'event_status': filters.get('event_status', ''),
            'event_ids': filters.get('selected_events', []),
            'organiser_ids': filters.get('selected_organisers', []),
            'selected_user_ids': filters.get('selected_users', []),
            'exclude_admins': filters.get('exclude_admins', False),
            'exclude_inactive': filters.get('exclude_inactive', False),
            'exclude_unconfirmed_email': filters.get('exclude_unconfirmed_email', False),
        },
    )
    return obj


def _populate_recipients(mail: AdminEmailQueue, recipients: list[dict]) -> int:
    mail.recipients.all().delete()

    objs = []
    seen: set[str] = set()
    for r in recipients:
        email_lower = r['email'].strip().lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)
        objs.append(AdminEmailQueueRecipient(
            mail=mail,
            user_id=r.get('user_id'),
            email=r['email'],
            name=r.get('name', ''),
            reason=r.get('reason', ''),
        ))

    if objs:
        AdminEmailQueueRecipient.objects.bulk_create(objs, ignore_conflicts=True)

    return len(objs)


def _get_message_text(cd: dict) -> str:
    """Extract plain string from message field (handles LazyI18nString from I18nEmailBodyFormField)."""
    msg = cd.get('message', '')
    if msg is None:
        return ''
    if hasattr(msg, 'data'):
        data = msg.data
        if isinstance(data, dict):
            return data.get('en', '') or (next(iter(data.values()), '') if data else '')
        return str(data) if data else ''
    return str(msg) if msg else ''


PLACEHOLDER_GROUPS = {
    'user': [
        {'key': 'user_name', 'label': _('Full name'), 'example': 'Jane Doe'},
        {'key': 'first_name', 'label': _('First name'), 'example': 'Jane'},
        {'key': 'last_name', 'label': _('Last name'), 'example': 'Doe'},
        {'key': 'email', 'label': _('Email address'), 'example': 'jane@example.com'},
        {'key': 'account_url', 'label': _('Account URL'), 'example': 'https://eventyay.com/account/'},
    ],
    'organiser': [
        {'key': 'organiser_name', 'label': _('Organiser name'), 'example': 'FOSSASIA'},
        {'key': 'organiser_url', 'label': _('Organiser URL'), 'example': 'https://eventyay.com/organiser/fossasia/'},
    ],
    'event': [
        {'key': 'event_name', 'label': _('Event name'), 'example': 'FOSSASIA Summit 2026'},
        {'key': 'event_url', 'label': _('Event URL'), 'example': 'https://eventyay.com/event/fossasia-2026/'},
        {'key': 'event_start_date', 'label': _('Event start date'), 'example': '2026-03-14'},
        {'key': 'event_end_date', 'label': _('Event end date'), 'example': '2026-03-16'},
    ],
    'platform': [
        {'key': 'platform_name', 'label': _('Platform name'), 'example': 'Eventyay'},
        {'key': 'platform_url', 'label': _('Platform URL'), 'example': 'https://eventyay.com/'},
        {'key': 'support_email', 'label': _('Support email'), 'example': 'support@eventyay.com'},
        {'key': 'support_url', 'label': _('Support URL'), 'example': 'https://eventyay.com/support/'},
    ],
}

SAMPLE_CONTEXT = {
    'user_name': 'Jane Doe',
    'first_name': 'Jane',
    'last_name': 'Doe',
    'email': 'jane@example.com',
    'account_url': '#',
    'organiser_name': 'Example Organiser',
    'organiser_url': '#',
    'event_name': 'Example Event',
    'event_url': '#',
    'event_start_date': '2026-01-15',
    'event_end_date': '2026-01-17',
    'platform_name': 'Eventyay',
    'platform_url': '#',
    'support_email': 'support@eventyay.com',
    'support_url': '#',
}


class AdminMessageComposeView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/admin/messages/compose.html'
    form_class = AdminComposeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['draft_save'] = self.request.POST.get('action') == 'draft'
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        draft_pk = self.request.GET.get('draft')
        if draft_pk:
            draft = AdminEmailQueue.objects.filter(
                pk=draft_pk, status=AdminEmailStatus.DRAFT
            ).first()
            if draft:
                self._draft = draft
                initial.update({
                    'recipient_group': draft.recipient_group,
                    'subject': draft.subject,
                    'message': draft.message,
                    'reply_to': draft.reply_to,
                    'bcc': draft.bcc,
                    'scheduled_at': draft.scheduled_at,
                    'delivery_mode': 'later' if draft.scheduled_at else 'now',
                })
                try:
                    f = draft.filters
                    initial.update({
                        'account_status': f.account_status,
                        'user_role': f.user_role,
                        'language': f.language,
                        'event_status': f.event_status,
                        'created_after': f.created_after,
                        'created_before': f.created_before,
                        'last_active_after': f.last_active_after,
                        'last_active_before': f.last_active_before,
                        'exclude_admins': f.exclude_admins,
                        'exclude_inactive': f.exclude_inactive,
                        'exclude_unconfirmed_email': f.exclude_unconfirmed_email,
                    })
                    if f.organiser_ids:
                        initial['selected_organisers'] = Organizer.objects.filter(pk__in=f.organiser_ids)
                    if f.event_ids:
                        initial['selected_events'] = Event.objects.filter(pk__in=f.event_ids)
                    if f.selected_user_ids:
                        initial['selected_users'] = User.objects.filter(pk__in=f.selected_user_ids)
                except AdminEmailQueueFilter.DoesNotExist:
                    pass
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['draft'] = getattr(self, '_draft', None)
        ctx['output'] = getattr(self, 'output', None)
        ctx['recipient_count'] = getattr(self, 'recipient_count', 0)
        ctx['placeholders'] = PLACEHOLDER_GROUPS
        draft = ctx['draft']
        if draft and draft.recipient_count_snapshot is not None:
            current, _skipped = resolve_admin_recipients(_extract_filter_dict(ctx['form'].initial))
            if len(current) != draft.recipient_count_snapshot:
                ctx['recipient_count_changed'] = True
                ctx['old_recipient_count'] = draft.recipient_count_snapshot
                ctx['new_recipient_count'] = len(current)
        return ctx

    def form_valid(self, form):
        action = self.request.POST.get('action')
        cd = form.cleaned_data
        filters = _extract_filter_dict(cd)

        if action == 'test':
            test_email = cd.get('test_email')
            if not test_email:
                form.add_error('test_email', _('Please enter a test email address.'))
                return self.form_invalid(form)
            return self._send_test_email(form, test_email)

        if action == 'preview':
            recipients, _skipped = resolve_admin_recipients(filters)
            self.recipient_count = len(recipients)
            self.output = self._build_preview(cd)
            return self.render_to_response(self.get_context_data(form=form))

        is_draft = action == 'draft'

        draft = getattr(self, '_draft', None)
        draft_pk = self.request.POST.get('draft_id') or self.request.GET.get('draft')
        if draft_pk and not draft:
            draft = AdminEmailQueue.objects.filter(
                pk=draft_pk, status=AdminEmailStatus.DRAFT
            ).first()

        attachment = cd.get('attachment')

        if draft:
            mail = draft
            mail.recipient_group = cd['recipient_group']
            mail.subject = cd.get('subject', '')
            mail.message = _get_message_text(cd)
            mail.reply_to = cd.get('reply_to', '')
            mail.bcc = cd.get('bcc', '')
            mail.attachment = attachment.id if attachment else None
            mail.scheduled_at = cd.get('scheduled_at')
            mail.status = AdminEmailStatus.DRAFT if is_draft else AdminEmailStatus.QUEUED
            mail.user = self.request.user
        else:
            mail = AdminEmailQueue(
                user=self.request.user,
                recipient_group=cd['recipient_group'],
                subject=cd.get('subject', ''),
                message=_get_message_text(cd),
                reply_to=cd.get('reply_to', ''),
                bcc=cd.get('bcc', ''),
                attachment=attachment.id if attachment else None,
                scheduled_at=cd.get('scheduled_at'),
                status=AdminEmailStatus.DRAFT if is_draft else AdminEmailStatus.QUEUED,
            )

        if is_draft:
            resolved, _skipped = resolve_admin_recipients(filters)
            mail.recipient_count_snapshot = len(resolved)
            mail.save()
            _save_filters(mail, filters)
            LogEntry.objects.create(
                content_type=ContentType.objects.get_for_model(AdminEmailQueue),
                object_id=mail.pk,
                user=self.request.user,
                action_type='eventyay.admin.mail.draft_saved',
                data=json.dumps({
                    'admin_email_id': mail.pk,
                    'subject': mail.subject,
                    'recipient_group': mail.recipient_group,
                }),
            )
            messages.success(self.request, _('The draft has been saved.'))
            return redirect('eventyay_admin:admin.messages.drafts')

        resolved, _skipped = resolve_admin_recipients(filters)
        count = len(resolved)

        if count >= HIGH_RECIPIENT_THRESHOLD and not self.request.POST.get('confirm_send'):
            self.recipient_count = count
            ctx = self.get_context_data(form=form)
            ctx['confirm_high_count'] = True
            ctx['high_count'] = count
            ctx['confirm_send_token'] = _audience_fingerprint(filters, count)
            return self.render_to_response(ctx)

        if count >= HIGH_RECIPIENT_THRESHOLD:
            if self.request.POST.get('confirm_send') != _audience_fingerprint(filters, count):
                self.recipient_count = count
                ctx = self.get_context_data(form=form)
                ctx['confirm_high_count'] = True
                ctx['high_count'] = count
                ctx['confirm_send_token'] = _audience_fingerprint(filters, count)
                return self.render_to_response(ctx)

        mail.recipient_count_snapshot = count
        with transaction.atomic():
            mail.save()
            _save_filters(mail, filters)
            _populate_recipients(mail, resolved)

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=mail.pk,
            user=self.request.user,
            action_type='eventyay.admin.mail.queued',
            data=json.dumps({
                'admin_email_id': mail.pk,
                'recipient_count': count,
                'subject': mail.subject,
                'recipient_group': mail.recipient_group,
                'send_immediately': cd.get('send_immediately', False),
                'scheduled_at': mail.scheduled_at.isoformat() if mail.scheduled_at else None,
            }),
        )


        send_immediately = cd.get('send_immediately', False)
        if send_immediately:
            send_admin_email.apply_async(args=[mail.pk])
            messages.success(self.request, _('Your email is being sent to {count} recipients.').format(count=count))
        elif mail.scheduled_at:
            send_admin_email.apply_async(args=[mail.pk], eta=mail.scheduled_at)
            messages.success(
                self.request,
                _('Your email has been scheduled for {count} recipients.').format(count=count),
            )
        else:
            messages.success(
                self.request,
                _('Your email has been added to the outbox with {count} recipients.').format(count=count),
            )

        return redirect('eventyay_admin:admin.messages.outbox')

    def _send_test_email(self, form, test_email: str):

        cd = form.cleaned_data
        subject = cd.get('subject', _('(No subject)'))
        body = _get_message_text(cd)

        sample = dict(SAMPLE_CONTEXT)
        sample['email'] = test_email
        for key, value in sample.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        try:
            mail_send_task.apply_async(
                kwargs={
                    'to': [test_email],
                    'subject': f'[TEST] {subject}',
                    'body': body,
                    'html': AdminEmailQueue.make_html(body),
                    'reply_to': [cd.get('reply_to')] if cd.get('reply_to') else [],
                    'event': None,
                    'cc': [],
                    'bcc': [],
                    'attachments': None,
                },
                ignore_result=True,
            )
            messages.success(
                self.request,
                _('Test email sent successfully to {email}.').format(email=test_email),
            )
        except Exception:
            logger.exception('Failed to send test email')
            messages.error(
                self.request,
                _('Failed to send test email. Please check your mail configuration.'),
            )

        return self.render_to_response(self.get_context_data(form=form))

    def _build_preview(self, cd: dict) -> dict:
        subject = cd.get('subject', '')
        body = _get_message_text(cd)
        for key, value in SAMPLE_CONTEXT.items():
            subject = subject.replace('{' + key + '}', value)
            body = body.replace('{' + key + '}', value)

        return {
            'subject': subject,
            'html': AdminEmailQueue.make_html(body),
        }


class AdminMessageOutboxView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/outbox.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.QUEUED)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_count'] = AdminEmailQueue.objects.filter(status=AdminEmailStatus.QUEUED).count()
        return ctx


class AdminMessageDraftsView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/drafts.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.DRAFT)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-updated_at')
        )


class AdminMessageSentView(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = AdminEmailQueue
    template_name = 'pretixcontrol/admin/messages/sent.html'
    context_object_name = 'mails'
    paginate_by = 25

    def get_queryset(self):
        return (
            AdminEmailQueue.objects
            .filter(status=AdminEmailStatus.SENT)
            .annotate(recipient_count=Count('recipients'))
            .select_related('user')
            .order_by('-sent_at')
        )


class AdminMessageTemplatesView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/messages/templates.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['templates'] = self._get_platform_templates()
        return ctx

    def _get_platform_templates(self) -> list[dict]:


        templates = []
        for role_value, role_label in MailTemplateRoles.choices:
            templates.append({
                'name': str(role_label),
                'category': _('System'),
                'trigger': str(role_label),
                'recipient_type': _('User'),
                'role': role_value,
            })

        system_templates = [
            {'name': _('Account registration'), 'category': _('Account'), 'trigger': _('User registers')},
            {'name': _('Email confirmation'), 'category': _('Account'), 'trigger': _('Email verification sent')},
            {'name': _('Password reset'), 'category': _('Account'), 'trigger': _('Password reset requested')},
            {'name': _('Account notification'), 'category': _('Account'), 'trigger': _('Account status changed')},
            {'name': _('Organiser invitation'), 'category': _('Team'), 'trigger': _('Team invitation sent')},
            {'name': _('Event team invitation'), 'category': _('Team'), 'trigger': _('Event team invitation sent')},
            {'name': _('Billing validation'), 'category': _('Billing'), 'trigger': _('Billing validation requested')},
            {'name': _('Platform fee notification'), 'category': _('Billing'), 'trigger': _('Fee invoiced')},
            {'name': _('Ticket order confirmation'), 'category': _('Ticketing'), 'trigger': _('Order placed')},
            {'name': _('Ticket confirmation'), 'category': _('Ticketing'), 'trigger': _('Ticket confirmed')},
            {'name': _('Ticket cancellation'), 'category': _('Ticketing'), 'trigger': _('Order cancelled')},
            {'name': _('Refund notification'), 'category': _('Ticketing'), 'trigger': _('Refund processed')},
            {'name': _('CfP submission confirmation'), 'category': _('CfP'), 'trigger': _('Proposal submitted')},
            {'name': _('Proposal acceptance'), 'category': _('CfP'), 'trigger': _('Proposal accepted')},
            {'name': _('Proposal rejection'), 'category': _('CfP'), 'trigger': _('Proposal rejected')},
            {'name': _('Speaker schedule update'), 'category': _('Schedule'), 'trigger': _('Schedule updated')},
            {'name': _('Reviewer notification'), 'category': _('Review'), 'trigger': _('Review assigned')},
            {'name': _('Team member notification'), 'category': _('Team'), 'trigger': _('Team membership changed')},
            {'name': _('Video/event notification'), 'category': _('Video'), 'trigger': _('Video event updated')},
            {'name': _('System notification'), 'category': _('System'), 'trigger': _('System event')},
        ]
        for t in system_templates:
            t.setdefault('recipient_type', _('User'))
            t.setdefault('role', '')
        templates.extend(system_templates)

        return templates


class AdminMessageTemplateDetailView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/messages/template_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        role = self.kwargs.get('role', '')

        with scopes_disabled():
            template = MailTemplate.objects.filter(role=role).first()
        ctx['mail_template'] = template
        ctx['role'] = role
        ctx['role_label'] = dict(MailTemplateRoles.choices).get(role, role)
        return ctx


class AdminMessageSendView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk)

        if mail.status == AdminEmailStatus.SENT:
            messages.warning(request, _('This email has already been sent.'))
        elif mail.status == AdminEmailStatus.DRAFT:
            messages.warning(request, _('Drafts cannot be sent directly. Move to outbox first.'))
        else:
            send_admin_email.apply_async(args=[mail.pk])
            LogEntry.objects.create(
                content_type=ContentType.objects.get_for_model(AdminEmailQueue),
                object_id=mail.pk,
                user=request.user,
                action_type='eventyay.admin.mail.sent',
                data=json.dumps({'admin_email_id': mail.pk, 'subject': mail.subject}),
            )
            messages.success(request, _('The email has been queued for sending.'))

        return redirect('eventyay_admin:admin.messages.outbox')


class AdminMessageCancelView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        with transaction.atomic():
            mail = (
                AdminEmailQueue.objects
                .select_for_update()
                .filter(pk=pk, status=AdminEmailStatus.QUEUED)
                .first()
            )
            if mail is None:
                messages.warning(request, _('This email could not be cancelled (not found or already processed).'))
                return redirect('eventyay_admin:admin.messages.outbox')

            mail.status = AdminEmailStatus.CANCELLED
            mail.save(update_fields=['status'])

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=mail.pk,
            user=request.user,
            action_type='eventyay.admin.mail.cancelled',
            data=json.dumps({'admin_email_id': mail.pk, 'subject': mail.subject}),
        )

        messages.success(request, _('The email has been cancelled.'))
        return redirect('eventyay_admin:admin.messages.outbox')


class AdminMessageDeleteView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk, status=AdminEmailStatus.DRAFT)
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=pk,
            user=request.user,
            action_type='eventyay.admin.mail.deleted',
            data=json.dumps({'admin_email_id': pk, 'subject': mail.subject}),
        )
        mail.delete()
        messages.success(request, _('The draft has been deleted.'))
        return redirect('eventyay_admin:admin.messages.drafts')


class AdminMessageDuplicateView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        mail = get_object_or_404(AdminEmailQueue, pk=pk)
        new_mail = mail.duplicate()
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(AdminEmailQueue),
            object_id=new_mail.pk,
            user=request.user,
            action_type='eventyay.admin.mail.duplicated',
            data=json.dumps({'source_id': pk, 'new_id': new_mail.pk, 'subject': new_mail.subject}),
        )
        messages.success(request, _('The email has been duplicated as a draft.'))
        return redirect(new_mail.get_edit_url())


class AdminMessagePreviewView(StaffMemberRequiredMixin, View):
    """AJAX endpoint — sanitises and renders admin email preview HTML."""

    def post(self, request):
        content_type = request.content_type or ''
        if 'application/json' not in content_type:
            logger.debug('AdminMessagePreviewView: unexpected content_type %r', content_type)
            return JsonResponse({'html': AdminEmailQueue.make_html('')})

        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'html': ''}, status=400)

        raw_html = payload.get('html', '')
        if not isinstance(raw_html, str):
            return JsonResponse({'html': ''}, status=400)

        safe_html = sanitize_email_html(raw_html)
        preview_html = safe_html
        for key, value in SAMPLE_CONTEXT.items():
            preview_html = preview_html.replace('{' + key + '}', str(value))

        return JsonResponse({'html': AdminEmailQueue.make_html(preview_html)})


class AdminMessageRecipientsView(AdministratorPermissionRequiredMixin, View):
    def get(self, request):
        form = AdminComposeRecipientsForm(data=request.GET)
        if not form.is_valid():
            return JsonResponse({'count': 0, 'recipients': [], 'errors': form.errors}, status=400)

        filters = _extract_filter_dict(form.cleaned_data)
        recipients, skipped = resolve_admin_recipients(filters)

        preview = [
            {
                'name': r['name'],
                'email': r['email'],
                'status': r.get('status', ''),
                'role': r.get('role', ''),
                'reason': r.get('reason', ''),
            }
            for r in recipients[:100]
        ]

        return JsonResponse({
            'count': len(recipients),
            'skipped': skipped,
            'recipients': preview,
        })
