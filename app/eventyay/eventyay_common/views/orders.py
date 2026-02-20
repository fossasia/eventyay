from logging import getLogger
from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.views.generic.list import ListView

from eventyay.base.models import Order, User

from ..forms.filters import UserOrderFilterForm


logger = getLogger(__name__)


class MyOrdersView(LoginRequiredMixin, ListView):
    template_name = 'eventyay_common/orders/orders.html'
    paginate_by = 20

    def get_queryset(self):
        user = cast(User, self.request.user)
        queryset = Order.objects.annotate(email_lower=Lower('email')).select_related('event')
        # The user.email_addresses already contains lowercased emails
        queryset = queryset.filter(Q(email_lower__in=user.email_addresses)).order_by('-datetime')

        # Filter by event if provided
        filter_form = UserOrderFilterForm(self.request.GET, user=user)
        if filter_form.is_valid():
            event = filter_form.cleaned_data['event']
            if event:
                queryset = queryset.filter(event=event)

        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = UserOrderFilterForm(self.request.GET, user=self.request.user)
        return ctx

    def get(self, request, *args, **kwargs):
        filter_form = UserOrderFilterForm(self.request.GET, user=self.request.user)
        # If filter form is invalid, strip the 'event' from URL and redirect to this new URL.
        if not filter_form.is_valid():
            new_url_query = request.GET.copy()
            new_url_query.pop('event', None)
            new_url = request.path + '?' + new_url_query.urlencode()
            logger.info('To redirect to "%s" because the filter values are invalid.', new_url)
            return redirect(new_url)
        return super().get(request, *args, **kwargs)
