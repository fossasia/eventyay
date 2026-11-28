from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, View
from django_scopes import scope

from eventyay.base.models import OrderPosition, Voucher
from eventyay.base.services.cart import CartError, CartManager
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.views import EventViewMixin
from eventyay.presale.views.cart import get_or_create_cart_id
from eventyay.presale.views.order import OrderDetailMixin, OrderProtectedActionMixin

from .forms import ResaleSellForm, ResaleSettingsForm
from .models import ResaleListing
from .services import (
    ResaleError,
    available_listings_qs,
    calculate_seller_payout,
    create_listing,
    is_position_eligible,
    max_allowed_price,
    marketplace_is_open,
    release_expired_reservations,
    reserve_listing,
    withdraw_listing,
)
from .settings import marketplace_is_open as settings_marketplace_is_open


class ResaleSettingsView(EventSettingsViewMixin, EventSettingsFormView):
    form_class = ResaleSettingsForm
    template_name = 'pretixplugins/resale/settings.html'
    permission = 'can_change_event_settings'

    def get_success_url(self):
        return reverse(
            'plugins:resale:settings',
            kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug},
        )


class ResaleOverviewView(EventPermissionRequiredMixin, ListView):
    template_name = 'pretixplugins/resale/overview.html'
    permission = 'can_view_orders'
    context_object_name = 'listings'
    paginate_by = 50

    def get_queryset(self):
        release_expired_reservations(self.request.event)
        qs = ResaleListing.objects.filter(event=self.request.event).select_related(
            'position',
            'position__product',
            'seller_order',
            'buyer_order',
            'refund',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event
        qs = ResaleListing.objects.filter(event=event)
        ctx['counts'] = {
            'available': qs.filter(status=ResaleListing.STATUS_AVAILABLE).count(),
            'reserved': qs.filter(status=ResaleListing.STATUS_RESERVED).count(),
            'sold': qs.filter(status=ResaleListing.STATUS_SOLD).count(),
            'withdrawn': qs.filter(status=ResaleListing.STATUS_WITHDRAWN).count(),
            'refund_pending': qs.filter(refund_status=ResaleListing.REFUND_PENDING).count(),
            'refund_failed': qs.filter(refund_status=ResaleListing.REFUND_FAILED).count(),
            'fees': sum(
                (listing.fee_amount for listing in qs.filter(status=ResaleListing.STATUS_SOLD)),
                Decimal('0.00'),
            ),
        }
        ctx['status_filter'] = self.request.GET.get('status', '')
        return ctx


class ResaleAdminWithdrawView(EventPermissionRequiredMixin, View):
    permission = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        listing = get_object_or_404(ResaleListing, event=request.event, pk=kwargs['listing'])
        try:
            withdraw_listing(listing=listing)
            messages.success(request, _('The listing has been withdrawn.'))
        except ResaleError as exc:
            messages.error(request, str(exc))
        return redirect(
            reverse(
                'plugins:resale:overview',
                kwargs={'organizer': request.event.organizer.slug, 'event': request.event.slug},
            )
        )


class ResaleSellView(OrderProtectedActionMixin, EventViewMixin, OrderDetailMixin, FormView):
    template_name = 'pretixplugins/resale/sell.html'
    form_class = ResaleSellForm

    @cached_property
    def position(self):
        with scope(organizer=self.request.event.organizer, event=self.request.event):
            return get_object_or_404(
                OrderPosition.objects.select_related('order', 'product', 'variation'),
                pk=self.kwargs['position'],
                order=self.order,
                canceled=False,
            )

    def dispatch(self, request, *args, **kwargs):
        if not self.order:
            raise Http404()
        if not settings_marketplace_is_open(request.event):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['max_price'] = max_allowed_price(self.position)
        return kwargs

    def get_initial(self):
        return {'price': max_allowed_price(self.position)}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        price = self.position.price
        form = kwargs.get('form') or self.get_form()
        if form.is_bound and form.is_valid():
            price = form.cleaned_data['price']
        elif form['price'].value():
            try:
                price = Decimal(str(form['price'].value()))
            except Exception:
                price = self.position.price
        fee, payout = calculate_seller_payout(self.request.event, price)
        ctx.update(
            {
                'order': self.order,
                'position': self.position,
                'original_price': self.position.price,
                'fee': fee,
                'payout': payout,
            }
        )
        return ctx

    def form_valid(self, form):
        ok, reason = is_position_eligible(self.request.event, self.position)
        if not ok:
            messages.error(self.request, reason)
            return self.form_invalid(form)
        try:
            create_listing(event=self.request.event, position=self.position, price=form.cleaned_data['price'])
        except ResaleError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, _('Your ticket has been listed on the marketplace.'))
        return redirect(self.get_order_url())


class ResaleWithdrawView(OrderProtectedActionMixin, EventViewMixin, OrderDetailMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not self.order:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        listing = get_object_or_404(
            ResaleListing,
            pk=kwargs['listing'],
            seller_order=self.order,
            event=request.event,
        )
        try:
            withdraw_listing(listing=listing)
            messages.success(request, _('Your listing has been withdrawn.'))
        except ResaleError as exc:
            messages.error(request, str(exc))
        return redirect(self.get_order_url())


class MarketplaceView(EventViewMixin, TemplateView):
    template_name = 'pretixplugins/resale/marketplace.html'

    def get(self, request, *args, **kwargs):
        if 'eventyay.plugins.resale' not in request.event.get_plugins():
            raise Http404()
        if not request.event.settings.get('resale_enabled', as_type=bool):
            raise Http404()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        release_expired_reservations(self.request.event)
        ctx['listings'] = available_listings_qs(self.request.event)
        ctx['marketplace_open'] = marketplace_is_open(self.request.event)
        ctx['suspended'] = self.request.event.settings.get('resale_suspended', as_type=bool)
        return ctx


class MarketplaceBuyView(EventViewMixin, View):
    """Reserve a listing and add a sold-out-safe cart position via a one-shot voucher."""

    def post(self, request, *args, **kwargs):
        if not marketplace_is_open(request.event):
            messages.error(request, _('The ticket marketplace is not open.'))
            return redirect(self.get_marketplace_url())

        listing = get_object_or_404(
            ResaleListing.objects.select_related('position', 'position__product', 'position__variation'),
            event=request.event,
            pk=kwargs['listing'],
        )
        try:
            if not request.session.session_key:
                request.session.create()
            listing = reserve_listing(listing=listing, session_key=request.session.session_key)
            cart_id = get_or_create_cart_id(request)
            self._add_listing_to_cart(request, listing, cart_id)
        except (ResaleError, CartError) as exc:
            messages.error(request, str(exc))
            return redirect(self.get_marketplace_url())

        request.session['resale_listing_id'] = listing.pk
        request.session[f'resale_cart_{cart_id}'] = listing.pk
        minutes = request.event.settings.get('resale_reservation_minutes', as_type=int) or 30
        messages.info(
            request,
            _(
                'Ticket reserved. Complete checkout and payment within {minutes} minutes '
                'or the reservation will expire.'
            ).format(minutes=minutes),
        )
        return redirect(
            eventreverse(request.event, 'presale:event.checkout.start', kwargs={})
        )

    def _add_listing_to_cart(self, request, listing: ResaleListing, cart_id: str):
        with transaction.atomic(), scope(organizer=request.event.organizer, event=request.event):
            voucher = Voucher.objects.create(
                event=request.event,
                code=f'RESALE-{listing.pk}-{get_random_string(8).upper()}',
                max_usages=1,
                redeemed=0,
                valid_until=listing.reserved_until or now(),
                block_quota=False,
                allow_ignore_quota=True,
                price_mode='set',
                value=listing.price,
                product=listing.position.product,
                variation=listing.position.variation,
                subevent=listing.position.subevent,
                tag=f'resale:{listing.pk}',
                comment=_('Auto voucher for ticket resale listing {id}').format(id=listing.pk),
            )
            cm = CartManager(event=request.event, cart_id=cart_id, sales_channel=getattr(request, 'sales_channel', 'web'))
            cm.add_new_products(
                [
                    {
                        'product': listing.position.product_id,
                        'variation': listing.position.variation_id,
                        'count': 1,
                        'custom_price': None,
                        'voucher': voucher.code,
                        'seat': None,
                        'subevent': listing.position.subevent_id,
                    }
                ]
            )
            cm.commit()

    def get_marketplace_url(self):
        return reverse(
            'plugins:resale:marketplace',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )
