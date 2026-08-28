from datetime import datetime, time
from logging import getLogger

from django.db.models import Q
from django.shortcuts import redirect
from django.utils.timezone import get_current_timezone, make_aware
from django.views.generic.list import ListView

from eventyay.base.models import Order
from eventyay.control.views import PaginationMixin

from ..forms.filters import UserOrderFilterForm


logger = getLogger(__name__)


class MyOrdersView(PaginationMixin, ListView):
    template_name = 'eventyay_common/orders/orders.html'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.filter(Q(email__iexact=user.email)).select_related('event').order_by('-datetime')

        filter_form = UserOrderFilterForm(self.request.GET, user=user, request=self.request)
        if filter_form.is_valid():
            fdata = filter_form.cleaned_data
            if fdata.get('event'):
                qs = qs.filter(event=fdata['event'])

            if fdata.get('code'):
                code_query = fdata['code'].strip()
                if code_query:
                    qs = qs.filter(
                        Q(code__icontains=code_query)
                        | Q(code__icontains=Order.normalize_code(code_query))
                    )

            if fdata.get('status'):
                qs = qs.filter(status=fdata['status'])

            tz = get_current_timezone()
            if fdata.get('date_from'):
                start_dt = make_aware(datetime.combine(fdata['date_from'], time.min), tz)
                qs = qs.filter(datetime__gte=start_dt)

            if fdata.get('date_to'):
                end_dt = make_aware(datetime.combine(fdata['date_to'], time.max), tz)
                qs = qs.filter(datetime__lte=end_dt)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = UserOrderFilterForm(self.request.GET, user=self.request.user, request=self.request)
        return ctx

    def get(self, request, *args, **kwargs):
        filter_form = UserOrderFilterForm(self.request.GET, user=self.request.user, request=self.request)
        # If filter form is invalid, strip invalid keys from URL and redirect to new URL.
        if not filter_form.is_valid():
            new_url_query = request.GET.copy()
            for field_name in filter_form.errors:
                new_url_query.pop(field_name, None)
            new_url = request.path
            if new_url_query:
                new_url += '?' + new_url_query.urlencode()
            logger.info('To redirect to "%s" because the filter values are invalid.', new_url)
            return redirect(new_url)
        return super().get(request, *args, **kwargs)
