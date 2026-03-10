from django.conf import settings
from django.db.models import F, Max, Min, Prefetch
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import ListView

from eventyay.base.models import Event, EventMetaValue, Organizer, Quota
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.control.forms.filter import EventFilterForm
from eventyay.control.permissions import OrganizerPermissionRequiredMixin
from eventyay.control.views import PaginationMixin


class EventList(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'pretixcontrol/events/index.html'

    def get_queryset(self):
        qs = (
            self.request.user.get_events_with_any_permission(self.request)
            .prefetch_related(
                'organizer',
                '_settings_objects',
                'organizer___settings_objects',
                'organizer__meta_properties',
                Prefetch(
                    'meta_values',
                    EventMetaValue.objects.select_related('property'),
                    to_attr='meta_values_cached',
                ),
            )
            .order_by('-date_from')
        )

        qs = qs.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
        ).annotate(
            order_from=Coalesce('min_from', 'date_from'),
            order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
        )

        qs = qs.prefetch_related(
            Prefetch(
                'quotas',
                queryset=Quota.objects.filter(subevent__isnull=True).annotate(s=Coalesce(F('size'), 0)).order_by('-s'),
                to_attr='first_quotas',
            )
        )

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        orga_c = Organizer.objects.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True)).count()
        ctx['hide_orga'] = orga_c <= 1
        ctx['meta_fields'] = [self.filter_form[k] for k in self.filter_form.fields if k.startswith('meta_')]

        quotas = []
        for s in ctx['events']:
            s.first_quotas = s.first_quotas[:4]
            quotas += list(s.first_quotas)

        qa = QuotaAvailability(early_out=False)
        for q in quotas:
            qa.queue(q)
        qa.compute()

        for q in quotas:
            q.cached_avail = qa.results[q]
            q.cached_availability_paid_orders = qa.count_paid_orders.get(q, 0)
            if q.size is not None:
                q.percent_paid = min(
                    100,
                    round(q.cached_availability_paid_orders / q.size * 100) if q.size > 0 else 100,
                )
        return ctx

    @cached_property
    def filter_form(self):
        return EventFilterForm(data=self.request.GET, request=self.request)


class SlugRNG(OrganizerPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # See Order.assign_code
        charset = list('abcdefghjklmnpqrstuvwxyz3789')
        for i in range(100):
            val = get_random_string(length=settings.ENTROPY['order_code'], allowed_chars=charset)
            if not self.request.organizer.events.filter(slug__iexact=val).exists():
                break

        return JsonResponse({'slug': val})
