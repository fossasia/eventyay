import logging

from django.utils.translation import gettext_lazy as _

from eventyay.base.services.mail import SendMailException, mail


logger = logging.getLogger(__name__)


def send_team_invitation_email(
    *,
    user,
    organizer_name,
    team_name,
    url,
    locale,
    is_registered_user,
):
    """
    Send a team invitation email to a user.
    Args:
        user: The user object being invited
        organizer_name: Name of the organizer
        team_name: Name of the team
        url: The invitation or dashboard URL
        locale: Language code for the email
        is_registered_user: Boolean indicating if user is already registered
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        mail(
            user.primary_email,
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
            user.primary_email,
            team_name,
        )
        return False
