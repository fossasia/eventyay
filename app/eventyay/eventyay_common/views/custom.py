from allauth.account.views import ConfirmEmailView as AllauthConfirmEmailView
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _


class ConfirmEmailView(AllauthConfirmEmailView):
    """Custom email confirmation view that separates HTML from translatable strings."""

    # Explicitly use the Jinja template override located in jinja-templates/account/
    template_name = 'account/email_confirm.jinja'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build message components separately for better translation
        if context.get('confirmation'):
            confirmation = context['confirmation']
            email = confirmation.email_address.email
            user_display = confirmation.email_address.user.get_full_name() or confirmation.email_address.user.email

            # Store components separately for the template
            context['confirmation_email'] = email
            context['confirmation_user'] = user_display
            context['confirmation_message'] = _(
                'Please confirm that %(email)s is an email address for user %(user)s.'
            ) % {'email': email, 'user': user_display}
            context['already_confirmed_message'] = _(
                'Unable to confirm %(email)s because it is already confirmed by a different account.'
            ) % {'email': email}

        email_url = reverse('eventyay_common:account.email')
        context['email_url'] = email_url

        # Build invalid/expired link message without embedding HTML in translatable strings
        if not context.get('confirmation'):
            action_text = _('issue a new email confirmation request')
            link_html = f'<a href="{email_url}">{action_text}</a>'
            message = _(
                'This email confirmation link expired or is invalid. Please %(email_action_link)s.'
            ) % {'email_action_link': link_html}
            context['invalid_confirmation_message'] = mark_safe(message)

        return context
