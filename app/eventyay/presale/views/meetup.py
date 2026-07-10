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

from eventyay.base.models import Quota
from eventyay.base.models.orders import Order, OrderPayment, OrderPosition
from eventyay.base.models.product import Product
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.views import EventViewMixin


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


class MeetupRsvpView(EventViewMixin, View):

    def get(self, request, *args, **kwargs):
        return redirect(eventreverse(request.event, 'presale:event.index'))

    def post(self, request, *args, **kwargs):
        if request.event.settings.get('event_type') != 'meetup':
            raise Http404

        with scope(event=request.event):
            try:
                product = request.event.products.filter(admission=True, active=True).first()
                if product is None:
                    raise Product.DoesNotExist
                quota = product.quotas.filter(size__isnull=True).first()
                if quota is None:
                    quota = product.quotas.first()
                if quota is None:
                    raise Quota.DoesNotExist
            except (Product.DoesNotExist, Quota.DoesNotExist):
                raise Http404

        if not request.event.presale_is_running:
            messages.error(request, _('Registration for this event is not currently open.'))
            return redirect(eventreverse(request.event, 'presale:event.index'))

        if request.user.is_authenticated:
            return self._handle_authenticated_rsvp(request, product, quota)
        else:
            return self._handle_guest_rsvp(request, product, quota)

    def _handle_authenticated_rsvp(self, request, product, quota):
        with scope(event=request.event):
            existing = request.event.orders.filter(
                email=request.user.email,
                status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
            ).first()

        if existing:
            return redirect(eventreverse(request.event, 'presale:event.index'))

        name = getattr(request.user, 'fullname', None) or getattr(request.user, 'name', None) or request.user.email
        order = self._create_rsvp_order(
            request,
            email=request.user.email,
            locale=getattr(request, 'LANGUAGE_CODE', 'en'),
            product=product,
            attendee_name_parts={'_legacy': str(name)},
            attendee_email=request.user.email,
        )
        return redirect(eventreverse(request.event, 'presale:event.index'))

    def _handle_guest_rsvp(self, request, product, quota):
        if request.event.settings.require_registered_account_for_tickets:
            messages.error(request, _('Please log in to register for this event.'))
            return redirect(eventreverse(request.event, 'presale:event.index'))

        form = GuestRsvpForm(data=request.POST)
        if not form.is_valid():
            request._rsvp_guest_form = form
            from eventyay.presale.views.event import EventIndex
            view = EventIndex()
            view.setup(request, *self._args, **self._kwargs)
            return view.get(request, *self._args, **self._kwargs)

        cd = form.cleaned_data
        order = self._create_rsvp_order(
            request,
            email=cd['attendee_email'],
            locale=getattr(request, 'LANGUAGE_CODE', 'en'),
            product=product,
            attendee_name_parts={'_legacy': cd['attendee_name']},
            attendee_email=cd['attendee_email'],
        )
        # Store guest registration in session
        request.session[f'meetup_rsvp_{request.event.pk}'] = {
            'code': order.code,
            'secret': order.secret,
        }
        return redirect(eventreverse(request.event, 'presale:event.index'))

    def _create_rsvp_order(self, request, email, locale, product, attendee_name_parts, attendee_email):
        with scope(event=request.event), transaction.atomic():
            order = Order(
                status=Order.STATUS_PENDING,
                event=request.event,
                email=email,
                locale=locale,
                total=Decimal('0.00'),
                datetime=now(),
                sales_channel='web',
                require_approval=False,
                testmode=request.event.testmode,
                meta_info='{}',
            )
            order.set_expires(now(), [])
            order.save()

            pos = OrderPosition(
                order=order,
                product=product,
                price=Decimal('0.00'),
                tax_rate=Decimal('0.00'),
                tax_value=Decimal('0.00'),
                positionid=1,
                attendee_name_parts=attendee_name_parts,
                attendee_email=attendee_email,
            )
            pos.secret = secrets.token_hex(16)
            pos.pseudonymization_id = secrets.token_hex(8)
            pos.save()

            payment = order.payments.create(
                state=OrderPayment.PAYMENT_STATE_CREATED,
                provider='free',
                amount=Decimal('0.00'),
            )
            try:
                payment.confirm(send_mail=True, lock=False)
            except Exception:
                raise

            order.refresh_from_db()
        return order

    def dispatch(self, request, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        return super().dispatch(request, *args, **kwargs)
