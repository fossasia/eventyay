from allauth.account.views import EmailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse

from ...navigation import get_account_navigation
from .common import AccountMenuMixIn


class EmailAddressManagementView(LoginRequiredMixin, AccountMenuMixIn, EmailView):
    template_name = 'eventyay_common/account/email_management.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_items'] = get_account_navigation(self.request)
        return ctx

    def get_success_url(self):
        # Override the success URL to use our custom URL instead of allauth's default
        return reverse('eventyay_common:account.email')
