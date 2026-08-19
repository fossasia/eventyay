import secrets
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_scopes import scope

from eventyay.base.meetup import get_rsvp_product_and_quota, is_meetup_event
from eventyay.base.models import Quota
from eventyay.base.models.orders import Order, OrderPayment, OrderPosition
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.views import EventViewMixin

MEETUP_RSVP_SESSION_KEY = 'meetup_rsvp_registered_{}'
RSVP_ORDER_STATUSES = (Order.STATUS_PAID, Order.STATUS_PENDING)


class GuestRsvpForm(forms.Form):
    attendee_name = forms.CharField(
        label=_('Your name'),
        max_length=255,
        error_messages={'required': _('Your name is required.')},
    )
    attendee_email = forms.EmailField(
        label=_('Your email'),
        error_messages={
            'required': _('A valid email address is required.'),
            'invalid': _('A valid email address is required.'),
        },
    )


def has_rsvp_order(event, email) -> bool:
    if not email:
        return False
    with scope(organizer=event.organizer):
        return event.orders.filter(email__iexact=email, status__in=RSVP_ORDER_STATUSES).exists()


class MeetupRsvpView(EventViewMixin, View):

    def get(self, request, *args, **kwargs):
        return self._redirect_to_index(request)

    def post(self, request, *args, **kwargs):
        if not is_meetup_event(request.event):
            raise Http404

        product, quota = get_rsvp_product_and_quota(request.event)
        if product is None or quota is None:
            raise Http404

        if not request.event.presale_is_running:
            messages.error(request, _('Registration for this event is not currently open.'))
            return self._redirect_to_index(request)

        if request.user.is_authenticated:
            return self._register_user(request, product)
        return self._register_guest(request, product)

    def _redirect_to_index(self, request):
        return redirect(eventreverse(request.event, 'presale:event.index'))

    def _register_user(self, request, product):
        email = request.user.email
        if has_rsvp_order(request.event, email):
            return self._redirect_to_index(request)

        name = (
            getattr(request.user, 'fullname', None)
            or getattr(request.user, 'name', None)
            or email
        )
        order = self._create_rsvp_order(request, product, email=email, name=str(name))
        if order is None:
            messages.error(request, _('Sorry, this event is already full.'))
        return self._redirect_to_index(request)

    def _register_guest(self, request, product):
        if request.event.settings.require_registered_account_for_tickets:
            messages.error(request, _('Please log in to register for this event.'))
            return self._redirect_to_index(request)

        form = GuestRsvpForm(data=request.POST)
        if not form.is_valid():
            return self._render_index_with_form_errors(request, form)

        order = self._create_rsvp_order(
            request,
            product,
            email=form.cleaned_data['attendee_email'],
            name=form.cleaned_data['attendee_name'],
        )
        if order is None:
            messages.error(request, _('Sorry, this event is already full.'))
            return self._redirect_to_index(request)

        request.session[MEETUP_RSVP_SESSION_KEY.format(request.event.pk)] = order.code
        return self._redirect_to_index(request)

    def _render_index_with_form_errors(self, request, form):
        # Imported here to break the circular import with the presale event views.
        from eventyay.presale.views.event import EventIndex

        request._rsvp_guest_form = form
        view = EventIndex()
        view.setup(request, *self.args, **self.kwargs)
        return view.get(request, *self.args, **self.kwargs)

    def _create_rsvp_order(self, request, product, email, name):
        with transaction.atomic():
            _, rsvp_quota = get_rsvp_product_and_quota(request.event)
            with scope(organizer=request.event.organizer):
                if rsvp_quota is not None:
                    quota = Quota.objects.select_for_update().get(pk=rsvp_quota.pk)
                    avail, count = quota.availability()
                    if avail != Quota.AVAILABILITY_OK:
                        return None

                order = Order(
                    status=Order.STATUS_PENDING,
                    event=request.event,
                    email=email,
                    locale=getattr(request, 'LANGUAGE_CODE', 'en'),
                    total=Decimal('0.00'),
                    datetime=now(),
                    sales_channel='web',
                    require_approval=False,
                    testmode=request.event.testmode,
                    meta_info='{}',
                )
                order.set_expires(now(), [])
                order.save()

                position = OrderPosition(
                    order=order,
                    product=product,
                    price=Decimal('0.00'),
                    tax_rate=Decimal('0.00'),
                    tax_value=Decimal('0.00'),
                    positionid=1,
                    attendee_name_parts={'_legacy': name},
                    attendee_email=email,
                )
                position.secret = secrets.token_hex(16)
                position.pseudonymization_id = secrets.token_hex(8)
                position.save()

                payment = order.payments.create(
                    state=OrderPayment.PAYMENT_STATE_CREATED,
                    provider='free',
                    amount=Decimal('0.00'),
                )
                payment.confirm(send_mail=True, lock=False)

                order.refresh_from_db()
        return order
