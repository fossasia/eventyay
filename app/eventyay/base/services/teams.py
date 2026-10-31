import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models.functions import Lower
from django.dispatch import receiver
from django.urls import NoReverseMatch
from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.auth import get_auth_backends
from eventyay.base.entitlements import EntitlementDecision, check_entitlement
from eventyay.base.models import Organizer
from eventyay.base.models.auth import User
from eventyay.base.models.organizer import (
    TEAM_INVITE_REMINDER_AFTER,
    TEAM_INVITE_VALIDITY,
    TeamInvite,
    generate_invite_token,
)
from eventyay.base.services.mail import SendMailException, mail
from eventyay.base.signals import periodic_task
from eventyay.eventyay_common.video.traits_sync import sync_video_traits_for_team
from eventyay.helpers.periodic import minimum_interval
from eventyay.helpers.urls import build_absolute_uri


logger = logging.getLogger(__name__)

TEAMSHIFTS_PLUGIN_REGEX = r'(^|,)teamshifts(,|$)'

TEAM_INVITATION_SUBJECT = _('Invitation to join the “{team}” team for “{event}”')
TEAM_INVITATION_TEXT = _(
    """Hello,

{organizer} has invited you to join the “{team}” team for “{event}”.

Open the following link to accept or decline the invitation:

{url}

You will only become a member of the team after you accept the invitation.
The invitation is valid for 48 hours, until {expires}.

If you do not want to join the team, you can decline the invitation or ignore this email.

Best regards,
Your eventyay team"""
)
TEAM_INVITATION_NEW_ACCOUNT_SUBJECT = _('Invitation to join eventyay and the “{team}” team for “{event}”')
TEAM_INVITATION_NEW_ACCOUNT_TEXT = _(
    """Hello,

You have been invited to join the eventyay platform and become a team member
of the “{team}” team for “{event}”, organized by {organizer}.

To respond, first create an eventyay account for this email address using the following link:

{url}

Creating an account does not automatically accept the team invitation.
After you have signed up, you can accept or decline it.
The invitation is valid for 48 hours, until {expires}.

If you do not want to join the team, you can ignore this email.

Best regards,
Your eventyay team"""
)
TEAM_INVITATION_REMINDER_SUBJECT = _('Reminder: Invitation to join the “{team}” team for “{event}”')
TEAM_INVITATION_REMINDER_TEXT = _(
    """Hello,

Your invitation from {organizer} to join the “{team}” team for “{event}” is still pending.

It will expire in about 24 hours, on {expires}. Open the following link to accept or decline it:

{url}

If you do not want to join the team, you can ignore this email.

Best regards,
Your eventyay team"""
)

TEAM_INVITATION_MAIL_TEMPLATES = (
    {
        'key': 'team-invitation',
        'name': _('Team invitation for an existing eventyay user'),
        'trigger': _('An organizer invites someone who already has an eventyay account'),
        'subject': TEAM_INVITATION_SUBJECT,
        'text': TEAM_INVITATION_TEXT,
    },
    {
        'key': 'team-invitation-new-account',
        'name': _('Team invitation for a person without an eventyay account'),
        'trigger': _('An organizer invites an email address without an eventyay account'),
        'subject': TEAM_INVITATION_NEW_ACCOUNT_SUBJECT,
        'text': TEAM_INVITATION_NEW_ACCOUNT_TEXT,
    },
    {
        'key': 'team-invitation-reminder',
        'name': _('Pending team invitation reminder'),
        'trigger': _('A team invitation is still pending 24 hours after it was sent'),
        'subject': TEAM_INVITATION_REMINDER_SUBJECT,
        'text': TEAM_INVITATION_REMINDER_TEXT,
    },
)


def get_team_invitation_mail_template(key):
    return next((template for template in TEAM_INVITATION_MAIL_TEMPLATES if template['key'] == key), None)


def preview_team_invitation_mail(template, *, event_name, organizer_name):
    """Render a team invitation template with example values, for read-only previews."""
    context = {
        'team': str(_('Program committee')),
        'event': event_name,
        'organizer': organizer_name,
        'url': build_absolute_uri('eventyay_common:auth.invite', kwargs={'token': 'example-token'}),
        'expires': date_format(now() + TEAM_INVITE_VALIDITY, 'SHORT_DATETIME_FORMAT'),
    }
    return str(template['subject']).format(**context), str(template['text']).format(**context)


class TeamInviteError(Exception):
    """Raised when a team invitation cannot be created, resent or answered."""


def check_full_admin_limit(team, email=None, user=None):
    """
    Enforce full-admin entitlement before adding a member or invite.
    Returns the EntitlementDecision. If decision.allowed is False, the fallback
    message is set on decision.message if it was empty.
    """
    if not team.can_change_organizer_settings:
        return EntitlementDecision(allowed=True)

    # Skip if the user/email already has full-admin access
    if user and user.teams.filter(organizer=team.organizer, can_change_organizer_settings=True).exists():
        return EntitlementDecision(allowed=True)
    if (
        not user
        and email
        and User.objects.filter(
            email__iexact=email,
            teams__organizer=team.organizer,
            teams__can_change_organizer_settings=True,
        ).exists()
    ):
        return EntitlementDecision(allowed=True)
    if (
        email
        and TeamInvite.objects.open()
        .filter(
            team__organizer=team.organizer,
            team__can_change_organizer_settings=True,
            email__iexact=email,
        )
        .exists()
    ):
        return EntitlementDecision(allowed=True)

    # Lock the organizer row to serialize concurrent checks
    Organizer.objects.select_for_update().filter(pk=team.organizer_id).first()

    admin_member_emails = set(
        User.objects.filter(
            teams__organizer=team.organizer,
            teams__can_change_organizer_settings=True,
        )
        .annotate(email_lower=Lower('email'))
        .values_list('email_lower', flat=True)
    )
    current_users = len(admin_member_emails)

    # Exclude invites whose email already belongs to an existing admin member
    current_invites = (
        TeamInvite.objects.open()
        .filter(
            team__organizer=team.organizer,
            team__can_change_organizer_settings=True,
        )
        .annotate(email_lower=Lower('email'))
        .exclude(
            email_lower__in=admin_member_emails,
        )
        .distinct()
        .count()
    )

    decision = check_entitlement(
        team.organizer,
        'organizer.full_admins',
        quantity=current_users + current_invites + 1,
    )
    if not decision.allowed and not decision.message:
        decision.message = str(_('You have reached the maximum limit for this feature on your current plan.'))

    return decision


def _get_teamshifts_events(team):
    return list(team.events.filter(plugins__regex=TEAMSHIFTS_PLUGIN_REGEX).order_by('pk')[:2])


def _get_teamshifts_member_url(team):
    if team.pk:
        events = _get_teamshifts_events(team)
        if len(events) == 1:
            try:
                return build_absolute_uri(
                    'plugins:teamshifts:dashboard',
                    kwargs={'organizer': team.organizer.slug, 'event': events[0].slug},
                )
            except NoReverseMatch:
                pass
    return build_absolute_uri('eventyay_common:dashboard')


def get_team_invitation_url(team):
    """Return the page a new team member should land on after joining ``team``."""
    if team.teamshifts_role:
        return _get_teamshifts_member_url(team)

    if team.pk:
        return build_absolute_uri(
            'eventyay_common:organizer.team',
            kwargs={'organizer': team.organizer.slug, 'team': team.pk},
        )

    return build_absolute_uri(
        'eventyay_common:organizer.teams',
        kwargs={'organizer': team.organizer.slug},
    )


def get_team_invite_event_name(team) -> str:
    """Name the event a team invitation is for, falling back to the organizer for multi-event teams."""
    if not team.all_events:
        with scopes_disabled():
            events = list(team.limit_events.all()[:2])
        if len(events) == 1:
            return str(events[0].name)
    return str(team.organizer.name)


def invite_belongs_to(invite, user) -> bool:
    """Whether ``user`` is the intended recipient of ``invite``."""
    if invite.user_id:
        return invite.user_id == user.pk
    return bool(user.email) and user.email.casefold() == (invite.email or '').casefold()


def _format_invite_expiry(invite) -> str:
    timezone_name = getattr(invite.user, 'timezone', None) or settings.TIME_ZONE
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = ZoneInfo(settings.TIME_ZONE)
    expires = invite.expires.astimezone(timezone)
    return f'{date_format(expires, "SHORT_DATETIME_FORMAT")} ({timezone.key})'


def send_team_invite(invite, *, locale=None, reminder=False) -> bool:
    """Send the invitation (or reminder) email that matches the invitee's account status."""
    team = invite.team
    if reminder:
        subject, text = TEAM_INVITATION_REMINDER_SUBJECT, TEAM_INVITATION_REMINDER_TEXT
    elif invite.user_id:
        subject, text = TEAM_INVITATION_SUBJECT, TEAM_INVITATION_TEXT
    else:
        subject, text = TEAM_INVITATION_NEW_ACCOUNT_SUBJECT, TEAM_INVITATION_NEW_ACCOUNT_TEXT
    locale = getattr(invite.user, 'locale', None) or locale
    context = {
        'team': str(team.name),
        'event': get_team_invite_event_name(team),
        'organizer': str(team.organizer.name),
        'url': invite.invitation_url,
        'expires': _format_invite_expiry(invite),
    }
    try:
        mail(
            invite.email,
            subject,
            LazyI18nString.from_gettext(text),
            context,
            event=None,
            locale=locale,
            user=invite.user,
        )
    except SendMailException:
        logger.exception('Failed to send team invitation email to %s for team %s', invite.email, team.pk)
        return False
    return True


def invite_to_team(team, email, *, invited_by=None, locale=None, log_kwargs=None):
    """Create a pending invitation for ``email`` and email it once the transaction commits.

    Existing accounts are only bound to the invite; membership is granted on acceptance.
    """
    email = email.strip()
    log_kwargs = log_kwargs or {}
    user = User.objects.filter(email__iexact=email).first()
    if user and team.members.filter(pk=user.pk).exists():
        raise TeamInviteError(_('This user already has permissions for this team.'))
    if team.invites.open().filter(email__iexact=email).exists():
        raise TeamInviteError(_('This user already has been invited for this team.'))
    if not user and 'native' not in get_auth_backends():
        raise TeamInviteError(_('Users need to have a eventyay account before they can be invited.'))
    decision = check_full_admin_limit(team, email=email, user=user)
    if not decision.allowed:
        raise TeamInviteError(decision.message)

    team.invites.filter(email__iexact=email).delete()
    created = now()
    invite = team.invites.create(
        email=user.email if user else email,
        user=user,
        invited_by=invited_by,
        created=created,
        expires=created + TEAM_INVITE_VALIDITY,
    )
    team.log_action(
        'eventyay.team.invite.created',
        data={'email': invite.email, 'user': user.pk if user else None},
        **log_kwargs,
    )
    transaction.on_commit(lambda: send_team_invite(invite, locale=locale))
    return invite


def resend_team_invite(invite, *, locale=None, log_kwargs=None):
    """Resend an open invite, or issue a fresh invitation if it has expired or been declined."""
    if not invite.is_open:
        team = invite.team
        user = invite.user or User.objects.filter(email__iexact=invite.email).first()
        if user and team.members.filter(pk=user.pk).exists():
            raise TeamInviteError(_('This user already has permissions for this team.'))
        decision = check_full_admin_limit(team, email=invite.email, user=user)
        if not decision.allowed:
            raise TeamInviteError(decision.message)
        invite.user = user
        invite.token = generate_invite_token()
        invite.state = TeamInvite.State.PENDING
        invite.created = now()
        invite.expires = invite.created + TEAM_INVITE_VALIDITY
        invite.reminder_sent = None
        invite.responded = None
        invite.save()
    invite.team.log_action('eventyay.team.invite.resent', data={'email': invite.email}, **(log_kwargs or {}))
    transaction.on_commit(lambda: send_team_invite(invite, locale=locale))
    return invite


def _lock_open_invite(invite, user):
    invite = TeamInvite.all_objects.select_for_update().select_related('team__organizer').get(pk=invite.pk)
    if invite.is_expired:
        raise TeamInviteError(
            _('This invitation has expired. Please contact the event organizer if you still want to join the team.')
        )
    if invite.state != TeamInvite.State.PENDING:
        raise TeamInviteError(_('This invitation has already been answered.'))
    if not invite_belongs_to(invite, user):
        raise TeamInviteError(_('This invitation was sent to a different email address.'))
    return invite


def accept_team_invite(invite, user):
    """Add ``user`` to the invited team. Only the intended recipient can accept an open invite."""
    with transaction.atomic():
        invite = _lock_open_invite(invite, user)
        team = invite.team
        team.members.add(user)
        sync_video_traits_for_team(team, members=[user])
        invite.user = user
        invite.state = TeamInvite.State.ACCEPTED
        invite.responded = now()
        invite.save(update_fields=['user', 'state', 'responded'])
        team.log_action(
            'eventyay.team.member.joined',
            data={'email': user.email, 'invite_email': invite.email, 'user': user.pk},
            user=user,
        )
    return invite


def decline_team_invite(invite, user):
    with transaction.atomic():
        invite = _lock_open_invite(invite, user)
        invite.user = user
        invite.state = TeamInvite.State.DECLINED
        invite.responded = now()
        invite.save(update_fields=['user', 'state', 'responded'])
        invite.team.log_action(
            'eventyay.team.invite.declined',
            data={'email': invite.email, 'user': user.pk},
            user=user,
        )
    return invite


@receiver(signal=periodic_task)
@scopes_disabled()
@minimum_interval(minutes_after_success=10)
def process_team_invites(sender, **kwargs):
    """Expire overdue team invites and remind invitees once, a day before expiry."""
    current = now()
    TeamInvite.objects.filter(state=TeamInvite.State.PENDING, expires__lte=current).update(
        state=TeamInvite.State.EXPIRED
    )
    due = TeamInvite.objects.filter(
        state=TeamInvite.State.PENDING,
        reminder_sent__isnull=True,
        created__lte=current - TEAM_INVITE_REMINDER_AFTER,
        expires__gt=current,
    ).select_related('team__organizer', 'user')
    for invite in due:
        claimed = TeamInvite.objects.filter(pk=invite.pk, reminder_sent__isnull=True).update(reminder_sent=current)
        if claimed:
            send_team_invite(invite, reminder=True)
