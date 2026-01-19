from allauth.account.views import EmailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse

from .common import AccountMenuMixIn


# Override allauth's EmailView to add our menu and customize the success URL.
# The removal of email addresses is still handled by allauth's internal flows.
class EmailAddressManagementView(LoginRequiredMixin, AccountMenuMixIn, EmailView):
    template_name = 'eventyay_common/account/email-management.html'

    def get_success_url(self):
        # Override the success URL to use our custom URL instead of allauth's default
        return reverse('eventyay_common:account.email')
