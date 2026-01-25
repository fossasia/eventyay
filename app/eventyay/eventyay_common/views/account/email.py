from allauth.account.views import EmailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .common import AccountMenuMixIn


# Override allauth's EmailView to add our menu and customize the success URL.
# The removal of email addresses is still handled by allauth's internal flows.
class EmailAddressManagementView(LoginRequiredMixin, AccountMenuMixIn, EmailView):
    template_name = 'eventyay_common/account/email-management.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        emailaddress_radios = context.get('emailaddress_radios') or ()
        has_email_param = bool(self.request.POST.get('email'))
        has_checked_radio = any(
            getattr(radio, 'checked', False) for radio in emailaddress_radios
        )
        context['has_email_selection'] = has_email_param or has_checked_radio
        return context

    def post(self, request, *args, **kwargs):
        if (
            any(
                key in request.POST
                for key in (
                    'action_primary',
                    'action_send',
                    'action_remove',
                )
            )
            and not request.POST.get('email')
        ):
            messages.error(request, _('Please select an email address first.'))
            return redirect(self.get_success_url())

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        # Override the success URL to use our custom URL instead of allauth's default
        return reverse('eventyay_common:account.email')
