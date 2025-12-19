import logging
from urllib.parse import quote
from urllib.parse import quote, urlencode

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import View

from eventyay.base.services.cart import CartError
from eventyay.base.signals import validate_cart
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.checkoutflow import get_checkout_flow
from eventyay.presale.views import (
    allow_frame_if_namespaced,
    cart_exists,
    get_cart,
    iframe_entry_view_wrapper,
)

logger = logging.getLogger(__name__)


@method_decorator((allow_frame_if_namespaced, iframe_entry_view_wrapper), 'dispatch')
class CheckoutView(View):
    def get_index_url(self, request):
        kwargs = {}
        if 'cart_namespace' in self.kwargs:
            kwargs['cart_namespace'] = self.kwargs['cart_namespace']
        return eventreverse(self.request.event, 'presale:event.index', kwargs=kwargs) + '?require_cookie=true'

    def dispatch(self, request, *args, **kwargs):
        self.request = request

        if not cart_exists(request) and 'async_id' not in request.GET:
            messages.error(request, _('Your cart is empty'))
            return self.redirect(self.get_index_url(self.request))

        if not request.event.presale_is_running:
            messages.error(request, _('The presale for this event is over or has not yet started.'))
            new_url = self.get_index_url(self.request)
            logger.info('Redirecting to %s as presale is not running.', new_url)
            return self.redirect(new_url)

        # Check if login is required for checkout
        if request.event.settings.require_registered_account_for_tickets and not request.user.is_authenticated:
            messages.info(request, _('Please log in to complete your order.'))
            # Build the current checkout URL to return to after login
            # Use request.path instead of get_full_path() to prevent open redirect attacks
            next_url = request.path
            login_url = reverse('eventyay_common:auth.login')
            redirect_url = f'{login_url}?{urlencode({"next": next_url})}'
            logger.info('Redirecting to login as require_registered_account_for_tickets is enabled.')
            return redirect(redirect_url)

        cart_error = None
        try:
            validate_cart.send(sender=self.request.event, positions=get_cart(request))
        except CartError as e:
            cart_error = e

        flow = request._checkout_flow = get_checkout_flow(self.request.event)
        previous_step = None
        for step in flow:
            if not step.is_applicable(request):
                continue
            if step.requires_valid_cart and cart_error:
                messages.error(request, str(cart_error))
                new_url = previous_step.get_step_url(request) if previous_step else self.get_index_url(request)
                logger.info('Redirecting to %s as cart is invalid.', new_url)
                return self.redirect(new_url)

            if 'step' not in kwargs:
                new_url = step.get_step_url(request)
                logger.info('Redirecting to %s as no step is specified.', new_url)
                return self.redirect(new_url)
            is_selected = step.identifier == kwargs.get('step', '')
            if (
                'async_id' not in request.GET
                and not is_selected
                and not step.is_completed(request, warn=not is_selected)
            ):
                new_url = step.get_step_url(request)
                logger.info('Redirecting to %s as previous steps are not completed.', new_url)
                return self.redirect(new_url)
            if is_selected:
                if request.method.lower() in self.http_method_names:
                    handler = getattr(step, request.method.lower(), self.http_method_not_allowed)
                else:
                    handler = self.http_method_not_allowed
                logger.debug('Dispatching to step handler %s.', handler)
                return handler(request)
            else:
                previous_step = step
                step.c_is_before = True
                step.c_resolved_url = step.get_step_url(request)
        logger.warning('No matching step found in checkout flow.')
        raise Http404()

    def redirect(self, url):
        if 'cart_id' in self.request.GET:
            url += ('&' if '?' in url else '?') + 'cart_id=' + quote(self.request.GET.get('cart_id'))
        return redirect(url)
