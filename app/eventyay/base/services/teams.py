import logging

from django.db.models.functions import Lower
from django.urls import NoReverseMatch
from django.utils.translation import gettext_lazy as _

from eventyay.base.entitlements import EntitlementDecision, check_entitlement
from eventyay.base.models import Organizer
from eventyay.base.models.auth import User
from eventyay.base.models.organizer import TeamInvite
from eventyay.base.services.mail import SendMailException, mail


logger = logging.getLogger(__name__)


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
        and TeamInvite.objects.filter(
            team__organizer=team.organizer,
            team__can_change_organizer_settings=True,
            email__iexact=email,
        ).exists()
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
        TeamInvite.objects.filter(
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


def get_team_invitation_url(team):
    """
    Determine the invitation or landing URL for an added team member.

    If the team has a TeamShifts role assigned ('coordinator' or 'lead'),
    link directly to the TeamShifts organizer dashboard entry point if available.
    Otherwise, fall back to the standard organizer team management URL.
    """
    from eventyay.helpers.urls import build_absolute_uri

    organizer_slug = getattr(team.organizer, 'slug', team.organizer)
    if getattr(team, 'teamshifts_role', '') in ('coordinator', 'lead'):
        try:
            return build_absolute_uri(
                'plugins:teamshifts:organizer_dashboard',
                kwargs={'organizer': organizer_slug},
            )
        except NoReverseMatch:
            pass

    return build_absolute_uri(
        'eventyay_common:organizer.teams',
        kwargs={'organizer': organizer_slug},
    )


def send_team_invitation_email(
    *,
    user,
    organizer_name,
    team_name,
    url=None,
    team=None,
    locale,
    is_registered_user,
):
    """
    Send a team invitation email to a user.
    Args:
        user: The user object being invited
        organizer_name: Name of the organizer
        team_name: Name of the team
        url: The invitation or dashboard URL (optional if team is provided)
        team: The team object (used to derive url if url is None)
        locale: Language code for the email
        is_registered_user: Boolean indicating if user is already registered
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    if url is None:
        if team is None:
            return False
        try:
            url = get_team_invitation_url(team)
        except Exception:
            return False

    try:
        mail(
            user.email,
            _('eventyay account invitation'),
            'pretixcontrol/email/invitation.txt',
            {
                'user': user,
                'organizer': organizer_name,
                'team': team_name,
                'url': url,
                'is_registered_user': is_registered_user,
            },
            event=None,
            locale=locale,
        )
        return True
    except SendMailException:
        logger.exception(
            'Failed to send team invitation email to %s for team %s',
            user.email,
            team_name,
        )
        return False
