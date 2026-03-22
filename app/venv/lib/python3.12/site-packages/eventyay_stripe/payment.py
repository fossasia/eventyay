import hashlib
import json
import logging
import re
import urllib.parse
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urlencode

import stripe
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.gis.geoip2 import GeoIP2
from django.core import signing
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy as _, pgettext
from django_countries import countries
from django_countries.fields import Country
from geoip2.errors import AddressNotFoundError
from pydantic import ValidationError

from eventyay.base.decimal import round_decimal
from eventyay.base.forms import SecretKeySettingsField
from eventyay.base.forms.questions import guess_country
from eventyay.base.models import (
    Event, InvoiceAddress, Order, OrderPayment, OrderRefund, Quota,
)
from eventyay.base.payment import BasePaymentProvider, PaymentException
from eventyay.base.plugins import get_all_plugins
from eventyay.base.services.mail import SendMailException
from eventyay.base.settings import SettingsSandbox
from eventyay.helpers.countries import CachedCountries
from eventyay.helpers.http import get_client_ip
from eventyay.helpers.urls import build_absolute_uri as build_global_uri
from eventyay.multidomain.urlreverse import build_absolute_uri
from eventyay.presale.views.cart import cart_session

from . import __version__
from .forms import StripeKeyValidator
from .models import ReferencedStripeObject, RegisteredApplePayDomain
from .tasks import get_stripe_account_key, stripe_verify_domain
from .validation_models import (
    LatestCharge, PaymentInfoData, PaymentMethodDetails, Source,
)

logger = logging.getLogger(__name__)


class StripeSettingsHolder(BasePaymentProvider):
    """Manage Stripe provider settings"""
    identifier = "stripe_settings"
    verbose_name = _("Stripe")
    is_enabled = False
    is_meta = True

    def __init__(self, event: Event):
        super().__init__(event)
        self.settings = SettingsSandbox("payment", "stripe", event)

    def get_connect_url(self, request):
        """
            Authorize Stripe account and redirect to Stripe
            Refer: https://docs.stripe.com/connect/oauth-reference
            https://github.com/stripe/stripe-python/blob/master/examples/oauth.py
        """
        request.session["payment_stripe_oauth_event"] = request.event.pk
        if "payment_stripe_oauth_token" not in request.session:
            request.session["payment_stripe_oauth_token"] = get_random_string(32)
        authorize_url = stripe.OAuth.authorize_url(
            client_id=self.settings.connect_client_id,
            response_type='code',
            scope='read_write',
            state=request.session["payment_stripe_oauth_token"],
            redirect_uri=build_global_uri("plugins:eventyay_stripe:oauth.return")
        )
        return authorize_url

    def settings_content_render(self, request):
        if self.settings.connect_client_id and not self.settings.secret_key:
            # Use Stripe connect
            if not self.settings.connect_user_id:
                return (
                    "<p>{}</p>" "<a href='{}' class='btn btn-primary btn-lg'>{}</a>"
                ).format(
                    _(
                        "To accept payments via Stripe, you will need an account at Stripe. By clicking on the "
                        "following button, you can either create a new Stripe account connect eventyay to an existing "
                        "one."
                    ),
                    self.get_connect_url(request),
                    _("Connect with Stripe"),
                )
            return (
                "<button formaction='{}' class='btn btn-danger'>{}</button>"
            ).format(
                reverse(
                    "plugins:eventyay_stripe:oauth.disconnect",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                    },
                ),
                _("Disconnect from Stripe"),
            )
        else:
            message = _(
                'Please configure a %%(link)s to '
                'the following endpoint in order to automatically cancel orders when charges are refunded '
                'externally and to process asynchronous payment methods like SOFORT.'
            ) % {'link': '<a href="https://dashboard.stripe.com/account/webhooks">Stripe Webhook</a>'}
            return "<div class='alert alert-info'>{}<br /><code>{}</code></div>".format(
                message,
                build_global_uri("plugins:eventyay_stripe:webhook")
            )

    @property
    def settings_form_fields(self):
        if 'eventyay_resellers' in [p.module for p in get_all_plugins()]:
            moto_settings = [
                (
                    "reseller_moto",
                    forms.BooleanField(
                        label=_("Enable MOTO payments for resellers"),
                        help_text=(
                            _(
                                "Gated feature (needs to be enabled for your account by Stripe support first)"
                            )
                            + '<div class="alert alert-danger">%s</div>'
                            % _(
                                "We can flag the credit card transaction you make through the reseller interface as "
                                "MOTO (Mail Order / Telephone Order), which will exempt them from Strong Customer "
                                "Authentication (SCA) requirements. However: By enabling this feature, you will need to "
                                "fill out yearly PCI-DSS self-assessment forms like the 40 page SAQ D. Please "
                                "consult the %s for further information on this subject."
                                % '<a href="https://stripe.com/docs/security">{}</a>'.format(
                                    _("Stripe Integration security guide")
                                )
                            )
                        ),
                        required=False,
                    ),
                )
            ]
        else:
            moto_settings = []

        if self.settings.connect_client_id and not self.settings.secret_key:
            # Stripe connect
            if self.settings.connect_user_id:
                fields = [
                    (
                        "connect_user_name",
                        forms.CharField(label=_("Stripe account"), disabled=True),
                    ),
                    (
                        "connect_user_id",
                        forms.CharField(label=_("Stripe user id"), disabled=True),
                    ),
                    (
                        "endpoint",
                        forms.ChoiceField(
                            label=_("Endpoint"),
                            initial="live",
                            choices=(
                                ("live", pgettext("stripe", "Live")),
                                ("test", pgettext("stripe", "Testing")),
                            ),
                            help_text=_(
                                "If your event is in test mode, we will always use Stripe's test API, "
                                "regardless of this setting."
                            ),
                        ),
                    ),
                ]
            else:
                return {}
        else:
            allcountries = list(countries)
            allcountries.insert(0, ("", _("Select country")))

            fields = [
                (
                    "publishable_key",
                    forms.CharField(
                        label=_("Publishable key"),
                        help_text=_(
                            '<a target="_blank" rel="noopener" href="{docs_url}">{text}</a>'
                        ).format(
                            text=_(
                                "Click here for a tutorial on how to obtain the required keys"
                            ),
                            docs_url="https://docs.stripe.com/keys",
                        ),
                        validators=(StripeKeyValidator("pk_"),),
                    ),
                ),
                (
                    "secret_key",
                    SecretKeySettingsField(
                        label=_("Secret key"),
                        validators=(StripeKeyValidator(["sk_", "rk_"]),),
                    ),
                ),
                (
                    "merchant_country",
                    forms.ChoiceField(
                        choices=allcountries,
                        label=_("Merchant country"),
                        help_text=_(
                            "The country in which your Stripe-account is registered in. Usually, this is your "
                            "country of residence."
                        ),
                    ),
                ),
            ]

        d = OrderedDict(
            fields
            + [
                (
                    "method_card",
                    forms.BooleanField(
                        label=_("Credit card payments"),
                        required=False,
                    ),
                ),
                (
                    "method_ideal",
                    forms.BooleanField(
                        label=_("iDEAL"),
                        disabled=self.event.currency != "EUR",
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_alipay",
                    forms.BooleanField(
                        label=_("Alipay"),
                        disabled=self.event.currency
                        not in (
                            'EUR', 'AUD', 'CAD', 'GBP', 'HKD', 'JPY', 'NZD', 'SGD', 'USD'
                        ),
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_bancontact",
                    forms.BooleanField(
                        label=_("Bancontact"),
                        disabled=self.event.currency != "EUR",
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_sofort",
                    forms.BooleanField(
                        label=_("SOFORT"),
                        disabled=self.event.currency != "EUR",
                        help_text=(
                            _("Needs to be enabled in your Stripe account first.")
                            + '<div class="alert alert-warning">%s</div>'
                            % _(
                                "Despite the name, Sofort payments via Stripe are <strong>not</strong> processed "
                                "instantly but might take up to <strong>14 days</strong> to be confirmed in some cases. "
                                "Please only activate this payment method if your payment term allows for this lag."
                            )
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_eps",
                    forms.BooleanField(
                        label=_("EPS"),
                        disabled=self.event.currency != "EUR",
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_multibanco",
                    forms.BooleanField(
                        label=_("Multibanco"),
                        disabled=self.event.currency != "EUR",
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_przelewy24",
                    forms.BooleanField(
                        label=_("Przelewy24"),
                        disabled=self.event.currency not in ["EUR", "PLN"],
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    "method_wechatpay",
                    forms.BooleanField(
                        label=_("WeChat Pay"),
                        disabled=self.event.currency
                        not in ['AUD', 'CAD', 'EUR', 'GBP', 'HKD', 'JPY', 'SGD', 'USD'],
                        help_text=_(
                            "Needs to be enabled in your Stripe account first."
                        ),
                        required=False,
                    ),
                ),
                (
                    'method_mobilepay',
                    forms.BooleanField(
                        label=_('MobilePay'),
                        disabled=self.event.currency not in ['DKK', 'EUR', 'NOK', 'SEK'],
                        help_text=_('Some payment methods might need to be enabled in the settings of your Stripe account '
                                    'before they work properly.'),
                        required=False,
                    )
                ),
                (
                    'method_revolut_pay',
                    forms.BooleanField(
                        label='Revolut Pay',
                        disabled=self.event.currency not in ['EUR', 'GBP'],
                        help_text=_('Revolut Pay method might need to be enabled in the settings of your Stripe account '
                                    'before they work properly. Revolut Pay payments must be in currencies supported in your country.'),
                        required=False,
                    )
                ),
                (
                    'method_swish',
                    forms.BooleanField(
                        label=_('Swish'),
                        disabled=self.event.currency != 'SEK',
                        help_text=_('Swish method might need to be enabled in the settings of your Stripe account '
                                    'before they work properly.'),
                        required=False,
                    )
                ),
                (
                    'method_twint',
                    forms.BooleanField(
                        label='TWINT',
                        disabled=self.event.currency != 'CHF',
                        help_text=_('Some payment methods might need to be enabled in the settings of your Stripe account '
                                    'before they work properly.'),
                        required=False,
                    )
                ),
                (
                    'method_affirm',
                    forms.BooleanField(
                        label=_('Affirm'),
                        disabled=self.event.currency not in ['USD', 'CAD'],
                        help_text=' '.join([
                            str(_('Some payment methods might need to be enabled in the settings of your Stripe account '
                                'before they work properly.')),
                            str(_('Only available for payments between $50 and $30,000.'))
                        ]),
                        required=False,
                    )
                ),
                (
                    'method_klarna',
                    forms.BooleanField(
                        label=_('Klarna'),
                        disabled=self.event.currency not in [
                            'AUD', 'CAD', 'CHF', 'CZK', 'DKK', 'EUR', 'GBP', 'NOK', 'NZD', 'PLN', 'SEK', 'USD'
                        ],
                        help_text=' '.join([
                            str(_('Some payment methods might need to be enabled in the settings of your Stripe account '
                                'before they work properly.')),
                            str(_('Klarna and Stripe will decide which of the payment methods offered by Klarna are '
                                'available to the user.')),
                            str(_('Klarna\'s terms of services do not allow it to be used by charities or political '
                                'organizations.')),
                        ]),
                        required=False,
                    )
                ),
                (
                    'method_sepa_debit',
                    forms.BooleanField(
                        label=_('SEPA Direct Debit'),
                        disabled=self.event.currency != 'EUR',
                        help_text=(
                            _('Some payment methods might need to be enabled in the settings of your Stripe account '
                                'before work properly.') +
                            '<div class="alert alert-warning">%s</div>' % _(
                                'SEPA Direct Debit payments via Stripe are <strong>not</strong> processed '
                                'instantly but might take up to <strong>14 days</strong> to be confirmed in some cases. '
                                'Please only activate this payment method if your payment term allows for this lag.'
                            )),
                        required=False,
                    )
                ),
                (
                    'sepa_creditor_name',
                    forms.CharField(
                        label=_('SEPA Creditor Mandate Name'),
                        disabled=self.event.currency != 'EUR',
                        help_text=_('Please provide your SEPA Creditor Mandate Name, that will be displayed to the user.'),
                        required=False,
                        widget=forms.TextInput(
                            attrs={
                                'data-display-dependency': '#id_payment_stripe_method_sepa_debit',
                                'data-required-if': '#id_payment_stripe_method_sepa_debit'
                            }
                        ),
                    )
                ),
            ]
            + list(super().settings_form_fields.items())
            + moto_settings
        )
        d.move_to_end("_enabled", last=False)
        return d


class StripeErrorHandlerMixin:
    def handle_card_error(self, e, payment):
        err = e.json_body['error'] if e.json_body else {'message': str(e)}
        logger.exception('Stripe error: %s', err)
        payment.fail(info={'error': True, 'message': err['message']})
        raise PaymentException(_('Stripe reported an error: %s') % err['message'])

    def handle_stripe_error(self, e, payment):
        err = e.json_body.get('error', {'message': str(e)}) if e.json_body else {'message': str(e)}
        logger.exception('Stripe error: %s', err)
        if err.get('code') != 'idempotency_key_in_use':
            payment.fail(info={'error': True, 'message': err['message']})
            raise PaymentException(
                _(
                    'We had trouble communicating with Stripe. '
                    'Please try again and get in touch with us if this problem persists.'
                )
            )


class PaymentIntentFactory:
    def _get_amount(self, event, payment):
        places = settings.CURRENCY_PLACES.get(event.currency, 2)
        return int((payment.amount) * 10**places)

    def create_payment_intent(self, payment, event, payment_method_id, method,
                              confirmation_method, idempotency_key_seed, kwargs):
        base_params = {
            'amount': self._get_amount(event, payment),
            'currency': event.currency.lower(),
            'payment_method': payment_method_id,
            'payment_method_types': [method],
            'confirmation_method': confirmation_method,
            'confirm': True,
            'description': f"{event.slug.upper()}-{payment.order.code}",
            'metadata': {
                "order": str(payment.order.id),
                "event": event.id,
                "code": payment.order.code,
            },
            'idempotency_key': f"{event.id}{payment.order.code}{idempotency_key_seed}",
            'return_url': build_absolute_uri(
                event,
                "plugins:eventyay_stripe:sca.return",
                kwargs={
                    "order": payment.order.code,
                    "payment": payment.pk,
                    "hash": payment.order.tagged_secret("plugins:eventyay_stripe"),
                },
            ),
            'expand': ["latest_charge"]
        }
        base_params.update(kwargs)
        return stripe.PaymentIntent.create(**base_params)

    def retrieve_payment_intent(payment_info, kwargs):
        return stripe.PaymentIntent.retrieve(
            payment_info['id'],
            expand=["latest_charge"],
            **kwargs
        )


class StripeMethod(BasePaymentProvider):
    identifier = ""
    method = ""
    explanation = ""
    redirect_action_handling = "iframe"
    redirect_in_widget_allowed = True
    confirmation_method = "manual"
    verbose_name = ""

    def __init__(self, event: Event):
        super().__init__(event)
        self.settings = SettingsSandbox("payment", "stripe", event)
        # self.intent_params = method_config['intent_params']
        self.error_handler = StripeErrorHandlerMixin()
        self.intent_factory = PaymentIntentFactory()

    @property
    def test_mode_message(self):
        if self.settings.connect_client_id and not self.settings.secret_key:
            is_testmode = True
        else:
            is_testmode = (
                self.settings.secret_key and "_test_" in self.settings.secret_key
            )
        if is_testmode:
            return mark_safe(
                _(
                    'The Stripe plugin is operating in test mode. You can use one of <a {args}>many test '
                    'cards</a> to perform a transaction. No money will actually be transferred.'
                ).format(
                    args='href="https://stripe.com/docs/testing#cards" target="_blank"'
                )
            )
        return None

    @property
    def settings_form_fields(self):
        return {}

    @property
    def is_enabled(self) -> bool:
        return self.settings.get("_enabled", as_type=bool) and self.settings.get(
            f"method_{self.method}", as_type=bool
        )

    def payment_refund_supported(self, payment: OrderPayment) -> bool:
        return True

    def payment_partial_refund_supported(self, payment: OrderPayment) -> bool:
        return True

    def checkout_prepare(self, request, cart):
        payment_method_id = (
            request.POST.get(f"stripe_{self.method}_payment_method_id", "")
            or request.POST.get('stripe_payment_method_id', "")
        )
        request.session[f"payment_stripe_{self.method}_payment_method_id"] = (
            payment_method_id
        )
        if payment_method_id == "":
            messages.warning(
                request, _("You may need to enable JavaScript for Stripe payments.")
            )
            return False
        return True

    def payment_prepare(self, request, payment):
        return self.checkout_prepare(request, None)

    def _amount_to_decimal(self, cents):
        places = settings.CURRENCY_PLACES.get(self.event.currency, 2)
        return round_decimal(float(cents) / (10**places), self.event.currency)

    def _decimal_to_int(self, amount):
        places = settings.CURRENCY_PLACES.get(self.event.currency, 2)
        return int(amount * 10**places)

    def _get_amount(self, payment):
        return self._decimal_to_int(payment.amount)

    def _prepare_api_connect_args(self, payment):
        d = {}
        if (
            self.settings.connect_client_id
            and self.settings.connect_user_id
            and not self.settings.secret_key
        ):
            fee = Decimal("0.00")
            if self.settings.get("connect_app_fee_percent", as_type=Decimal):
                fee = round_decimal(
                    self.settings.get("connect_app_fee_percent", as_type=Decimal)
                    * payment.amount
                    / Decimal("100.00"),
                    self.event.currency,
                )
            if self.settings.connect_app_fee_max:
                fee = min(
                    fee, self.settings.get("connect_app_fee_max", as_type=Decimal)
                )
            if self.settings.get("connect_app_fee_min", as_type=Decimal):
                fee = max(
                    fee, self.settings.get("connect_app_fee_min", as_type=Decimal)
                )
            if fee:
                d["application_fee_amount"] = self._decimal_to_int(fee)
        if self.settings.connect_destination:
            d["transfer_data"] = {"destination": self.settings.connect_destination}
        return d

    def statement_descriptor(self, payment, length=22):
        return "{event}-{code} {eventname}".format(
            event=self.event.slug.upper(),
            code=payment.order.code,
            eventname=re.sub("[^a-zA-Z0-9 ]", "", str(self.event.name)),
        )[:length]

    @property
    def api_config(self):
        if self.settings.connect_client_id and self.settings.connect_user_id:
            return {
                "api_key": (
                    self.settings.connect_secret_key
                    if self.settings.get('endpoint', 'live') == 'live' and not self.event.testmode and self.settings.connect_secret_key != ''
                    else self.settings.connect_test_secret_key
                ),
                "stripe_account": self.settings.connect_user_id,
            }
        return {
            "api_key": self.settings.secret_key,
        }

    def _init_api(self):
        stripe.api_version = "2024-11-20.acacia"
        stripe.set_app_info(
            "eventyay-stripe",
            version=__version__,
            url="https://github.com/fossasia/eventyay-stripe"
        )

    def _intent_api_args(self, request, payment):
        return {}

    def is_moto(self, request, payment=None) -> bool:
        return False

    def checkout_confirm_render(self, request) -> str:
        """Override method"""
        template = get_template("plugins/stripe/checkout_payment_confirm.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "provider": self,
        }
        return template.render(ctx)

    def payment_pending_render(self, request, payment) -> str:
        if payment.info:
            payment_info = json.loads(payment.info)
        else:
            payment_info = None
        template = get_template("plugins/stripe/pending.html")
        context = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "provider": self,
            "order": payment.order,
            "payment": payment,
            "payment_info": payment_info,
            "payment_hash": hashlib.sha1(
                payment.order.secret.lower().encode()
            ).hexdigest(),
        }
        return template.render(context)

    def matching_id(self, payment: OrderPayment):
        return payment.info_data.get("id", None)

    def api_payment_details(self, payment: OrderPayment):
        return {
            "id": payment.info_data.get("id", None),
            "payment_method": payment.info_data.get("payment_method", None),
        }

    def payment_control_render(self, request, payment) -> str:
        payment_method_details = {}
        if payment.info:
            payment_info = json.loads(payment.info)
            if "amount" in payment_info:
                payment_info["amount"] /= 10 ** settings.CURRENCY_PLACES.get(
                    self.event.currency, 2
                )
            # add details to render
            if (
                "latest_charge" in payment_info
                and isinstance(payment_info.get("latest_charge"), dict)
            ):
                payment_method_details = (
                    payment_info.get("latest_charge", {})
                    .get("payment_method_details", {})
                )
        else:
            payment_info = None
        template = get_template("plugins/stripe/control.html")
        return template.render({
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "payment_info": payment_info,
            "payment": payment,
            "method": self.method,
            "provider": self,
            "details": payment_method_details
        })

    def _redirect_payment(self, intent, request, payment):
        if intent.status == "requires_action":
            payment.info = str(intent)
            payment.state = OrderPayment.PAYMENT_STATE_CREATED
            payment.save()
            return self._perform_sca_redirect(request, payment)
        if intent.status == "requires_confirmation":
            payment.info = str(intent)
            payment.state = OrderPayment.PAYMENT_STATE_CREATED
            payment.save()
            self._confirm_intent(request, payment)
        elif intent.status == "succeeded" and intent.latest_charge.paid:
            try:
                payment.info = str(intent)
                payment.confirm()
            except Quota.QuotaExceededException as e:
                raise PaymentException(str(e)) from e
            except SendMailException as e:
                raise PaymentException(
                    _("There was an error sending the confirmation mail.")
                ) from e
        elif intent.status == "processing":
            if request:
                messages.warning(
                    request,
                    _(
                        "Your payment is pending completion."
                        "We will inform you as soon as the payment completed."
                    ),
                )
            payment.info = str(intent)
            payment.state = OrderPayment.PAYMENT_STATE_PENDING
            payment.save()
        elif intent.status == "requires_payment_method":
            if request:
                messages.warning(
                    request, _("Your payment failed. Please try again.")
                )
            payment.fail(info=str(intent))
        else:
            logger.info("Charge failed: %s", intent)
            payment.fail(info=str(intent))
            raise PaymentException(
                _("Stripe reported an error: %s")
                % intent.last_payment_error.message
            )

    def payment_is_valid_session(self, request):
        return (
            request.session.get(f"payment_stripe_{self.method}_payment_method_id", "") != ""
        )

    def _perform_sca_redirect(self, request, payment):
        url = build_absolute_uri(
            self.event,
            'plugins:eventyay_stripe:sca',
            kwargs={
                'order': payment.order.code,
                'payment': payment.pk,
                'hash': payment.order.tagged_secret('plugins:eventyay_stripe'),
            }
        )

        if not self.redirect_in_widget_allowed and request.session.get('iframe_session', False):
            redirect_url = build_absolute_uri(self.event, 'plugins:eventyay_stripe:redirect')
            data = signing.dumps({'url': url, 'session': {}}, salt='safe-redirect')
            return f"{redirect_url}?{urlencode({'data': data})}"

        return url

    def _handle_intent_response(self, request, payment, intent=None):
        def create_payment_intent(self, payment, payment_method_id, idempotency_key_seed, request, params):
            return stripe.PaymentIntent.create(
                amount=self._get_amount(payment),
                currency=self.event.currency.lower(),
                payment_method=payment_method_id,
                payment_method_types=[self.method],
                confirmation_method=self.confirmation_method,
                confirm=True,
                description=f"{self.event.slug.upper()}-{payment.order.code}",
                metadata={
                    "order": str(payment.order.id),
                    "event": self.event.id,
                    "code": payment.order.code,
                },
                idempotency_key=f"{self.event.id}{payment.order.code}{idempotency_key_seed}",
                return_url=build_absolute_uri(
                    self.event,
                    "plugins:eventyay_stripe:sca.return",
                    kwargs={
                        "order": payment.order.code,
                        "payment": payment.pk,
                        "hash": payment.order.tagged_secret("plugins:eventyay_stripe"),
                    },
                ),
                expand=["latest_charge"],
                **self._prepare_api_connect_args(payment),
                **self.api_config,
                **self._intent_api_args(request, payment),
                **params,
            )

        def retrieve_payment_intent(payment_info):
            if 'id' in payment_info:
                return stripe.PaymentIntent.retrieve(
                    payment_info['id'],
                    expand=["latest_charge"],
                    **self.api_config
                )

        try:
            if self.payment_is_valid_session(request):
                method = f"payment_stripe_{self.method}_payment_method_id"
                payment_method_id = request.session.get(method)
                # create a new payment intent
                params = {}

                if self.method == "card":
                    params["statement_descriptor_suffix"] = self.statement_descriptor(payment)
                else:
                    params["statement_descriptor"] = self.statement_descriptor(payment)

                if self.is_moto(request, payment):
                    params["payment_method_options"] = {"card": {"moto": True}}

                params.update(self._prepare_api_connect_args(payment))
                params.update(self.api_config)
                params.update(self._intent_api_args(request, payment))
                intent = self.intent_factory.create_payment_intent(
                    payment=payment,
                    event=self.event,
                    payment_method_id=payment_method_id,
                    method=self.method,
                    confirmation_method=self.confirmation_method,
                    idempotency_key_seed=payment_method_id or payment.full_id,
                    kwargs=params
                )
                # intent = create_payment_intent(payment, payment_method_id, idempotency_key_seed, request, params)
            else:
                # get payment intent
                payment_info = json.loads(payment.info)
                if not intent and "id" in payment_info:
                    intent = retrieve_payment_intent(payment_info)
        except stripe.error.CardError as e:
            self.error_handler.handle_card_error(e, payment)
        except stripe.error.StripeError as e:
            self.error_handler.handle_stripe_error(e, payment)
        else:
            # stripe update: change source to intent
            ReferencedStripeObject.objects.get_or_create(
                reference=intent.id,
                defaults={"order": payment.order, "payment": payment},
            )
            # redirect payment by intent status
            self._redirect_payment(intent, request, payment)
            return None

    def _confirm_intent(self, request, payment):
        """Confirm the Payment Intent"""
        self._init_api()

        try:
            payment_info = json.loads(payment.info)

            intent = stripe.PaymentIntent.confirm(
                payment_info["id"],
                return_url=build_absolute_uri(
                    self.event,
                    "plugins:eventyay_stripe:sca.return",
                    kwargs={
                        "order": payment.order.code,
                        "payment": payment.pk,
                        "hash": payment.order.tagged_secret("plugins:eventyay_stripe"),
                    },
                ),
                expand=["latest_charge"],
                **self.api_config,
            )

            payment.info = str(intent)
            payment.save()

            self._handle_intent_response(request, payment)
        except stripe.error.CardError as e:
            if e.json_body:
                err = e.json_body["error"]
                logger.exception("Stripe error: %s", str(err))
            else:
                err = {"message": str(e)}
                logger.exception("Stripe error: %s", str(e))
            logger.info("Stripe card error: %s", str(err))
            payment.fail(
                info={
                    "error": True,
                    "message": err["message"],
                }
            )
            raise PaymentException(
                _("Stripe reported an error with your card: %s"), err["message"]
            ) from e
        except stripe.error.InvalidRequestError as e:
            if e.json_body:
                err = e.json_body["error"]
                logger.exception("Stripe error: %s", str(err))
            else:
                err = {"message": str(e)}
                logger.exception("Stripe error: %s", str(e))
            payment.fail(
                info={
                    "error": True,
                    "message": err["message"],
                }
            )
            raise PaymentException(
                _(
                    "We had trouble communicating with Stripe. Please try again and get in touch "
                    "with us if this problem persists."
                )
            ) from e

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        self._init_api()
        try:
            # Stripe version upgrade: change from source to payment intent
            return self._handle_intent_response(request, payment)
        except stripe.error.StripeError as e:
            self.error_handler.handle_stripe_error(e, payment)
        finally:
            method = f"payment_stripe_{self.method}_payment_method_id"
            if method in request.session:
                del request.session[method]

    def redirect(self, request, url):
        if request.session.get("iframe_session", False):
            signer = signing.Signer(salt="safe-redirect")
            return (
                build_absolute_uri(request.event, "plugins:eventyay_stripe:redirect")
                + "?url="
                + urllib.parse.quote(signer.sign(url))
            )
        else:
            return str(url)

    def shred_payment_info(self, obj: OrderPayment):
        if not obj.info:
            return
        d = json.loads(obj.info)
        new = {}
        if "source" in d:
            new["source"] = {
                "id": d["source"].get("id"),
                "type": d["source"].get("type"),
                "brand": d["source"].get("brand"),
                "last4": d["source"].get("last4"),
                "bank_name": d["source"].get("bank_name"),
                "bank": d["source"].get("bank"),
                "bic": d["source"].get("bic"),
                "card": {
                    "brand": d["source"].get("card", {}).get("brand"),
                    "country": d["source"].get("card", {}).get("cuntry"),
                    "last4": d["source"].get("card", {}).get("last4"),
                },
            }
        if "amount" in d:
            new["amount"] = d["amount"]
        if "currency" in d:
            new["currency"] = d["currency"]
        if "status" in d:
            new["status"] = d["status"]
        if "id" in d:
            new["id"] = d["id"]

        new["_shredded"] = True
        obj.info = json.dumps(new)
        obj.save(update_fields=["info"])

        for le in (
            obj.order.all_logentries()
            .filter(action_type="eventyay.plugins.stripe.event")
            .exclude(data="", shredded=True)
        ):
            d = le.parsed_data
            if "data" in d:
                for k, v in list(d["data"]["object"].items()):
                    if v not in ("reason", "status", "failure_message", "object", "id"):
                        d["data"]["object"][k] = "█"
                le.data = json.dumps(d)
                le.shredded = True
                le.save(update_fields=["data", "shredded"])

    @transaction.atomic()
    def execute_refund(self, refund: OrderRefund):
        self._init_api()

        payment_info = refund.payment.info_data
        OrderPayment.objects.select_for_update().get(pk=refund.payment.pk)

        if not payment_info:
            raise PaymentException(_("No payment information found."))

        try:
            if payment_info["id"].startswith("pi_"):
                # update stripe: change charges -> latest_charge attribute
                if "latest_charge" in payment_info and isinstance(payment_info.get("latest_charge"), dict):
                    chargeid = payment_info["latest_charge"]["id"]
                elif "latest_charge" in payment_info and isinstance(payment_info.get("latest_charge"), str):
                    chargeid = payment_info["latest_charge"]
                else:
                    chargeid = payment_info["charges"]["data"][0]["id"]
            else:
                chargeid = payment_info["id"]

            # stripe update: from Charge to Refund
            # doc: https://docs.stripe.com/api/refunds?lang=python
            r = stripe.Refund.create(
                charge=chargeid,
                amount=self._get_amount(refund),
                **self.api_config,
                **(
                    {"reverse_transfer": True}
                    if self.settings.connect_destination
                    else {}
                ),
            )
        except (
            stripe.error.InvalidRequestError,
            stripe.error.AuthenticationError,
            stripe.error.APIConnectionError,
        ) as e:
            if e.json_body and "error" in e.json_body:
                err = e.json_body["error"]
                logger.exception("Stripe error: %s", str(err))
            else:
                err = {"message": str(e)}
                logger.exception("Stripe error: %s", str(e))
            refund.info_data = err
            refund.state = OrderRefund.REFUND_STATE_FAILED
            refund.execution_date = now()
            refund.save()
            refund.order.log_action(
                "eventyay.event.order.refund.failed",
                {
                    "local_id": refund.local_id,
                    "provider": refund.provider,
                    "error": str(e),
                },
            )
            raise PaymentException(
                _(
                    "We had trouble communicating with Stripe. Please try again and contact "
                    "support if the problem persists."
                )
            ) from e
        except stripe.error.StripeError as err:
            logger.error("Stripe error: %s", str(err))
            raise PaymentException(_("Stripe returned an error")) from err
        else:
            refund.info = str(r)
            if r.status in ("succeeded", "pending"):
                refund.done()
            elif r.status in ("failed", "canceled"):
                refund.state = OrderRefund.REFUND_STATE_FAILED
                refund.execution_date = now()
                refund.save()


class Redirector(StripeMethod):
    """Stripe Redirect Payment Method via Stripe system"""
    redirect_action_handling = "redirect"
    verbose_name = ""

    def payment_is_valid_session(self, request):
        method = f"payment_stripe_{self.method}_payment_method_id"
        return method in request.session

    def checkout_prepare(self, request, cart):
        request.session[f"payment_stripe_{self.method}_payment_method_id"] = None
        return True

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": self.method,
            }
        }

    def payment_form_render(self, request) -> str:
        template = get_template(
            "plugins/stripe/checkout_payment_form_simple_noform.html"
        )
        context = {
            "event": self.event,
            "request": request,
            "settings": self.settings,
            "explanation": self.explanation,
        }
        return template.render(context)


class StripeCreditCard(StripeMethod):
    """Represent Stripe Credit Card payment method """
    identifier = "stripe"
    verbose_name = _("Credit card via Stripe")
    public_name = _("Credit card")
    method = "card"
    explanation = _("Stripe Payment via Credit Card")

    def payment_form_render(self, request, total) -> str:
        account = get_stripe_account_key(self)
        if not RegisteredApplePayDomain.objects.filter(
            account=account, domain=request.host
        ).exists():
            stripe_verify_domain.apply_async(args=(self.event.pk, request.host))

        template = get_template("plugins/stripe/checkout_payment_form_cc.html")
        ctx = {
            "request": request,
            "event": self.event,
            "total": self._decimal_to_int(total),
            "settings": self.settings,
            "is_moto": self.is_moto(request),
        }
        return template.render(ctx)

    def payment_is_valid_session(self, request):
        return bool(
            request.session.get("payment_stripe_payment_method_id") or
            request.session.get("payment_stripe_card_payment_method_id")
        )

    def checkout_prepare(self, request, cart):
        if "payment_stripe_brand" in request.session:
            request.session["payment_stripe_card_brand"] = request.session["payment_stripe_brand"]
        if "payment_stripe_last4" in request.session:
            request.session["payment_stripe_card_last4"] = request.session["payment_stripe_last4"]
        request.session['payment_stripe_card_brand'] = request.POST.get('stripe_card_brand', '')
        request.session['payment_stripe_card_last4'] = request.POST.get('stripe_card_last4', '')
        payment_method_id = (
            request.POST.get("stripe_card_payment_method_id", "")
            or request.POST.get('stripe_payment_method_id', "")
        )
        request.session["payment_stripe_card_payment_method_id"] = payment_method_id
        return super().checkout_prepare(request, cart)

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        self._init_api()
        try:
            return self._handle_intent_response(request, payment)
        finally:
            if "payment_stripe_payment_method_id" in request.session:
                del request.session["payment_stripe_payment_method_id"]
            if "payment_stripe_card_payment_method_id" in request.session:
                del request.session["payment_stripe_card_payment_method_id"]

    def is_moto(self, request, payment=None) -> bool:
        # We don't have a payment yet when checking if we should display the MOTO-flag
        # However, before we execute the payment, we absolutely have to check if the request-SalesChannel as well as
        # the order are tagged as a reseller-transaction. Else, a user with a valid reseller-session might be able
        # to place a MOTO transaction trough the WebShop.

        moto = (
            self.settings.get("reseller_moto", False, as_type=bool)
            and request.sales_channel.identifier == "resellers"
        )

        return moto and payment.order.sales_channel == "resellers" if payment else moto

    def _handle_intent_response(self, request, payment, intent=None):
        try:
            if self.payment_is_valid_session(request):
                payment_method_id = (
                    request.session.get(f'payment_stripe_{self.method}_payment_method_id')
                    or request.session.get('payment_stripe_payment_method_id')
                )
                # Create a payment intent
                # https://docs.stripe.com/api/payment_intents/create
                params = {}
                if self.is_moto(request, payment):
                    params['payment_method_options'] = {'card': {'moto': True}}

                statement_descriptor = self.statement_descriptor(payment)

                if self.method == "card":
                    params['statement_descriptor_suffix'] = statement_descriptor
                else:
                    params['statement_descriptor'] = statement_descriptor

                params.update(self._prepare_api_connect_args(payment))
                params.update(self.api_config)
                params.update(self._intent_api_args(request, payment))
                intent = self.intent_factory.create_payment_intent(
                    payment=payment,
                    event=self.event,
                    payment_method_id=payment_method_id,
                    method=self.method,
                    confirmation_method=self.confirmation_method,
                    idempotency_key_seed=payment_method_id or payment.full_id,
                    kwargs=params
                )
            else:
                payment_info = json.loads(payment.info)
                if not intent:
                    intent = self.intent_factory.retrieve_payment_intent(payment_info)

        except stripe.error.CardError as e:
            self.error_handler.handle_card_error(e, payment)

        except stripe.error.StripeError as e:
            self.error_handler.handle_stripe_error(e, payment)

        else:
            ReferencedStripeObject.objects.get_or_create(reference=intent.id,
                                                         defaults={'order': payment.order, 'payment': payment})
            self._redirect_payment(intent, request, payment)

    def _confirm_intent(self, request, payment):
        self._init_api()

        try:
            payment_info = json.loads(payment.info)

            intent = stripe.PaymentIntent.confirm(
                payment_info["id"],
                return_url=build_absolute_uri(
                    self.event,
                    "plugins:eventyay_stripe:sca.return",
                    kwargs={
                        "order": payment.order.code,
                        "payment": payment.pk,
                        "hash": hashlib.sha1(
                            payment.order.secret.lower().encode()
                        ).hexdigest(),
                    },
                ),
                expand=["latest_charge"],
                **self.api_config,
            )

            payment.info = str(intent)
            payment.save()

            self._handle_intent_response(request, payment)
        except stripe.error.CardError as e:
            err = e.json_body["error"] if e.json_body else {"message": str(e)}
            logger.exception('Stripe error: %s', err)
            logger.info('Stripe card error: %s', err)
            payment.fail(
                info={
                    "error": True,
                    "message": err["message"],
                }
            )
            raise PaymentException(
                _("Stripe reported an error with your card: %s") % err["message"]
            ) from e
        except stripe.error.InvalidRequestError as e:
            if e.json_body:
                err = e.json_body["error"]
                logger.exception("Stripe error: %s", str(err))
            else:
                err = {"message": str(e)}
                logger.exception("Stripe error: %s", str(e))
            payment.fail(
                info={
                    "error": True,
                    "message": err["message"],
                }
            )
            raise PaymentException(
                _(
                    "We had trouble communicating with Stripe. Please try again and get in touch "
                    "with us if this problem persists."
                )
            ) from e

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        card = None
        try:
            payment_data = PaymentInfoData(**pi)  # Validate the payment info data

            if payment_data.latest_charge:
                latest_charge = payment_data.latest_charge
                if isinstance(latest_charge, str):
                    latest_charge = stripe.Charge.retrieve(latest_charge, **self.api_config)
                    validated_charge = LatestCharge(payment_method_details=PaymentMethodDetails(**latest_charge.get("payment_method_details", {})))
                    card = validated_charge.payment_method_details.card
                elif isinstance(payment_data.latest_charge, LatestCharge):
                    card = latest_charge.payment_method_details.card

            # Handle source
            elif payment_data.source:
                validated_source = Source(**payment_data.source.model_dump())
                card = validated_source.card

            if not card:
                logger.error("Could not parse payment data")
                return super().payment_presale_render(payment)
            return (
                f"{self.public_name}: "
                f'{card.brand.title()} '
                f'************{card.last4 or "****"}, '
                f'{_("expires {month}/{year}").format(month=card.exp_month, year=card.exp_year)}'
            )
        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception("Could not parse payment data: %s", e)
            return super().payment_presale_render(payment)


class StripeIdeal(Redirector):
    """Represents the Stripe Ideal payment method integration."""
    identifier = "stripe_ideal"
    verbose_name = _("iDEAL via Stripe")
    public_name = _("iDEAL")
    method = "ideal"
    explanation = _("iDEAL payment via Stripe")
    redirect_in_widget_allowed = False

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        bank = None
        try:
            payment_data = PaymentInfoData(**pi)  # Validate the payment info data
            if payment_data.latest_charge:
                latest_charge = payment_data.latest_charge
                if isinstance(latest_charge, str):
                    latest_charge = stripe.Charge.retrieve(latest_charge, **self.api_config)
                if latest_charge.payment_method_details:
                    payment_method_details = payment_data.latest_charge.payment_method_details
                    if payment_method_details.ideal:
                        bank = payment_method_details.ideal.bank
            elif payment_data.source:
                bank = payment_data.source.ideal.bank
            else:
                bank = None
            bank = "" if bank is None else bank.replace("_", " ").title()
        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception("Could not parse payment data: %s", e)
            return super().payment_presale_render(payment)


class StripeAlipay(Redirector):
    """Represents the Stripe Alipay payment method integration."""
    identifier = "stripe_alipay"
    verbose_name = _("Alipay via Stripe")
    public_name = _("Alipay")
    method = "alipay"
    explanation = _(
        'Chinese payment system Alipay.'
    )
    confirmation_method = 'automatic'


class StripeBancontact(Redirector):
    """Represents the Stripe Bancontact payment method integration."""
    identifier = "stripe_bancontact"
    verbose_name = _("Bancontact via Stripe")
    public_name = _("Bancontact")
    method = "bancontact"
    confirmation_method = 'automatic'
    explanation = _(
        "Stripe payment via Bancontact - Belgium payment system."
    )

    def payment_form_render(self, request) -> str:
        template = get_template(
            "plugins/stripe/checkout_payment_form_simple.html"
        )
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            'explanation': self.explanation,
            "form": self.payment_form(request),
        }
        return template.render(ctx)

    @property
    def payment_form_fields(self):
        """Require Account holder for Bancontact payment"""
        return OrderedDict(
            [
                ("account", forms.CharField(label=_("Account holder"), min_length=3)),
            ]
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        try:
            return super().execute_payment(request, payment)
        finally:
            if f'payment_stripe_{self.method}_account' in request.session:
                del request.session[f'payment_stripe_{self.method}_account']

    def payment_is_valid_session(self, request):
        return request.session.get("payment_stripe_bancontact_account", "") != ""

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)
        if form.is_valid():
            request.session["payment_stripe_bancontact_payment_method_id"] = None
            request.session['payment_stripe_bancontact_account'] = form.cleaned_data[
                'account'
            ]
            return True
        return False

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        bank = None
        try:
            payment_data = PaymentInfoData(**pi)  # validate
            if payment_data.latest_charge and payment_data.latest_charge.payment_method_details:
                payment_method_details = payment_data.latest_charge.payment_method_details
                if payment_method_details.bankcontact:
                    bank = payment_method_details.bankcontact.bank_name
            elif payment_data.source:
                bank = payment_data.source.bankcontact.bank_name

            if not bank:
                logger.error("Could not parse payment data")
                return super().payment_presale_render(payment)
            return gettext(f"Bank account at {bank}")
        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception("Could not parse payment data %s", e)
            return super().payment_presale_render(payment)

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "bancontact",
                "giropay": {},
                "billing_details": {
                    "name": request.session.get(f"payment_stripe_{self.method}_account") or gettext("unknown name")
                },
            }
        }


class StripeSofort(StripeMethod):
    identifier = "stripe_sofort"
    verbose_name = _("SOFORT via Stripe")
    public_name = _("SOFORT")
    method = "sofort"
    redirect_in_widget_allowed = False
    explanation = _("Stripe payment via SOFORT - European countries")

    def payment_form_render(self, request) -> str:
        template = get_template(
            "plugins/stripe/checkout_payment_form_simple.html"
        )
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            'explanation': self.explanation,
            "form": self.payment_form(request),
        }
        return template.render(ctx)

    @property
    def payment_form_fields(self):
        return OrderedDict(
            [
                (
                    "bank_country",
                    forms.ChoiceField(
                        label=_("Country of your bank"),
                        choices=(
                            ("de", _("Germany")),
                            ("at", _("Austria")),
                            ("be", _("Belgium")),
                            ("nl", _("Netherlands")),
                            ("es", _("Spain")),
                        ),
                    ),
                ),
            ]
        )

    def payment_is_valid_session(self, request):
        return request.session.get("payment_stripe_sofort_bank_country", "") != ""

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)
        if form.is_valid():
            request.session["payment_stripe_sofort_bank_country"] = form.cleaned_data[
                "bank_country"
            ]
            return True
        return False

    def payment_can_retry(self, payment):
        return (
            payment.state != OrderPayment.PAYMENT_STATE_PENDING
            and self._is_still_available(order=payment.order)
        )

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        try:
            payment_data = PaymentInfoData(**pi)  # Validate the payment info data

            return gettext("Bank account {iban} at {bank}").format(
                iban=f'{payment_data.source.sofort.country}****{payment_data.source.sofort.iban_last4}',
                bank=payment_data.source.sofort.bank_name
            )
        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception("Could not parse payment data %s", e)
            return super().payment_presale_render(payment)

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "sofort",
                "sofort": {
                    "country": (request.session.get("payment_stripe_sofort_bank_country") or "DE").upper()
                },
            }
        }

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        try:
            return super().execute_payment(request, payment)
        finally:
            if f'payment_stripe_{self.method}_bank_country' in request.session:
                del request.session[f'payment_stripe_{self.method}_bank_country']


class StripeEPS(Redirector):
    """Represents the Stripe EPS payment method integration"""
    identifier = "stripe_eps"
    verbose_name = _("EPS via Stripe")
    public_name = _("EPS")
    method = "eps"
    redirect_in_widget_allowed = False
    explanation = _("EPS payment via Stripe  - Austria-based payment method")

    def payment_form_render(self, request) -> str:
        template = get_template(
            "plugins/stripe/checkout_payment_form_simple.html"
        )
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            'explanation': self.explanation,
            "form": self.payment_form(request),
        }
        return template.render(ctx)

    @property
    def payment_form_fields(self):
        return OrderedDict(
            [
                ("account", forms.CharField(label=_("Account holder"))),
            ]
        )

    def payment_is_valid_session(self, request):
        return request.session.get("payment_stripe_eps_payment_method_id", "") != ""

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)
        if form.is_valid():
            request.session["payment_stripe_eps_payment_method_id"] = None
            request.session["payment_stripe_eps_account"] = form.cleaned_data["account"]
            return True
        return False

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        bank = None
        try:
            payment_data = PaymentInfoData(**pi)  # Validate the payment info data
            if payment_data.latest_charge and payment_data.latest_charge.payment_method_details:
                payment_method_details = pi.latest_charge.payment_method_details
                if payment_method_details.eps:
                    bank = payment_method_details.eps.bank
            elif pi.source and pi.source.eps:
                bank = pi.source.eps.bank
            else:
                bank = ""
            bank = "" if bank is None else bank.replace("_", " ").title()

            return gettext(f"Bank account at {bank}")

        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception("Could not parse payment data: %s", e)
            return super().payment_presale_render(payment)

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "eps",
                "giropay": {},
                "billing_details": {
                    "name": request.session.get("payment_stripe_eps_account") or gettext("unknown name")
                },
            }
        }


class StripeMultibanco(Redirector):
    """Represents the Stripe Multibanco payment method integration"""
    identifier = "stripe_multibanco"
    verbose_name = _("Multibanco via Stripe")
    public_name = _("Multibanco")
    method = "multibanco"
    explanation = _("Multibanco payment via Stripe - Portuguese bank account")
    redirect_in_widget_allowed = False

    def _intent_api_args(self, request, payment):
        return {
            'payment_method_data': {
                'type': 'multibanco',
                'billing_details': {
                    "email": payment.order.email
                }
            }
        }


class StripePrzelewy24(Redirector):
    """Represents the Stripe Przelewy24 payment method integration"""
    identifier = "stripe_przelewy24"
    verbose_name = _("Przelewy24 via Stripe")
    public_name = _("Przelewy24")
    method = 'p24'
    explanation = _(
        'Przelewy24 via Stripe - Polish payment method'
    )
    redirect_in_widget_allowed = False

    @property
    def is_enabled(self) -> bool:
        return self.settings.get('_enabled', as_type=bool) and self.settings.get('method_przelewy24', as_type=bool)

    def _intent_api_args(self, request, payment):
        return {
            'payment_method_data': {
                'type': 'p24',
                'billing_details': {
                    "email": payment.order.email
                }
            }
        }

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        bank = None
        try:
            payment_data = PaymentInfoData(**pi)  # Validate the payment info data
            if payment_data.latest_charge and payment_data.latest_charge.payment_method_details:
                payment_method_details = payment_data.latest_charge
                if payment_method_details.p24:
                    bank = payment_method_details.p24.bank
            elif payment_data.source:
                bank = payment_data.source.p24.bank
            bank = "" if bank is None else bank.replace("_", " ").title()
            return gettext(f"Bank account at {bank}")
        except ValidationError as e:
            logger.exception("Validation error occurred: %s", e)
            return super().payment_presale_render(payment)
        except KeyError as e:
            logger.exception('Could not parse payment data: %s', e)
            return super().payment_presale_render(payment)


class StripeSwish(Redirector):
    identifier = 'stripe_swish'
    verbose_name = _('Swish via Stripe')
    public_name = _('Swish')
    method = 'swish'
    confirmation_method = 'automatic'
    explanation = _(
        'This payment method is available to users of the Swedish apps Swish and BankID. Please have your app '
        'ready.'
    )

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "swish",
            },
            "payment_method_options": {
                "swish": {
                    "reference": payment.order.full_code,
                },
            }
        }


class StripeWeChatPay(Redirector):
    """Represents the Stripe Webchat payment method integration"""
    identifier = "stripe_wechatpay"
    verbose_name = _("WeChat Pay via Stripe")
    public_name = _("WeChat Pay")
    method = 'wechat_pay'
    confirmation_method = 'automatic'
    explanation = _(
        'Stripe via Wechatpay - Chinese payment method'
    )

    @property
    def is_enabled(self) -> bool:
        return self.settings.get('_enabled', as_type=bool) and self.settings.get('method_wechatpay', as_type=bool)

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "wechat_pay",
            },
            "payment_method_options": {
                "wechat_pay": {
                    "client": "web"
                },
            }
        }


class StripeTwint(Redirector):
    identifier = 'stripe_twint'
    verbose_name = _('TWINT via Stripe')
    public_name = 'TWINT'
    method = 'twint'
    confirmation_method = 'automatic'
    explanation = _(
        'This payment method is available to users of the Swiss app TWINT. Please have your app '
        'ready.'
    )

    def is_allowed(self, request: HttpRequest, total: Decimal=None) -> bool:
        return super().is_allowed(request, total) and request.event.currency == "CHF" and total <= Decimal("5000.00")

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "twint",
            },
        }


class StripeMobilePay(Redirector):
    identifier = 'stripe_mobilepay'
    verbose_name = 'MobilePay via Stripe'
    public_name = 'MobilePay'
    method = 'mobilepay'
    confirmation_method = 'automatic'
    explanation = _(
        'This payment method is available to MobilePay app users in Denmark and Finland. Please have your app ready.'
    )

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "mobilepay",
            },
        }


class StripeRevolutPay(Redirector):
    verbose_name = _('Revolut Pay via Stripe')
    public_name = _('Revolut Pay')
    method = 'revolut_pay'
    confirmation_method = 'automatic'
    explanation = _(
        'This payment method is available to users of the Revolut app. Please keep your login information '
        'available.'
    )

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "revolut_pay",
            },
        }


class StripePayPal(Redirector):
    identifier = 'stripe_paypal'
    verbose_name = _('PayPal via Stripe')
    public_name = _('PayPal')
    method = 'paypal'


class StripeSEPADirectDebit(StripeMethod):
    identifier = 'stripe_sepa_debit'
    verbose_name = _('SEPA Debit via Stripe')
    public_name = _('SEPA Debit')
    method = 'sepa_debit'
    ia = InvoiceAddress()

    def payment_form_render(self, request: HttpRequest, total: Decimal, order: Order=None) -> str:
        def get_invoice_address():
            if order and getattr(order, 'invoice_address', None):
                request._checkout_flow_invoice_address = order.invoice_address
            if not hasattr(request, '_checkout_flow_invoice_address'):
                cs = cart_session(request)
                iapk = cs.get('invoice_address')
                if not iapk:
                    request._checkout_flow_invoice_address = InvoiceAddress()
                else:
                    try:
                        request._checkout_flow_invoice_address = InvoiceAddress.objects.get(pk=iapk, order__isnull=True)
                    except InvoiceAddress.DoesNotExist:
                        request._checkout_flow_invoice_address = InvoiceAddress()
            return request._checkout_flow_invoice_address

        cs = cart_session(request)
        self.ia = get_invoice_address()

        template = get_template('plugins/stripe/sepadirectdebit.html')
        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'form': self.payment_form(request),
            'explanation': self.explanation,
            'email': order.email if order else cs.get('email', '')
        }
        return template.render(ctx)

    @property
    def payment_form_fields(self):
        return OrderedDict(
            [
                ('accountname',
                 forms.CharField(
                     label=_('Account Holder Name'),
                     initial=self.ia.name,
                 )),
                ('line1',
                 forms.CharField(
                     label=_('Account Holder Street'),
                     required=False,
                     widget=forms.TextInput(
                         attrs={
                             'data-display-dependency': '#stripe_sepa_debit_country',
                             'data-required-if': '#stripe_sepa_debit_country'
                         }
                     ),
                     initial=self.ia.street,
                 )),
                ('postal_code',
                 forms.CharField(
                     label=_('Account Holder Postal Code'),
                     required=False,
                     widget=forms.TextInput(
                         attrs={
                             'data-display-dependency': '#stripe_sepa_debit_country',
                             'data-required-if': '#stripe_sepa_debit_country'
                         }
                     ),
                     initial=self.ia.zipcode,
                 )),
                ('city',
                 forms.CharField(
                     label=_('Account Holder City'),
                     required=False,
                     widget=forms.TextInput(
                         attrs={
                             'data-display-dependency': '#stripe_sepa_debit_country',
                             'data-required-if': '#stripe_sepa_debit_country'
                         }
                     ),
                     initial=self.ia.city,
                 )),
                ('country',
                 forms.ChoiceField(
                     label=_('Account Holder Country'),
                     required=False,
                     choices=CachedCountries(),
                     widget=forms.Select(
                         attrs={
                             'data-display-dependency': '#stripe_sepa_debit_country',
                             'data-required-if': '#stripe_sepa_debit_country'
                         }
                     ),
                     initial=self.ia.country or guess_country(self.event),
                 )),
            ])

    def _intent_api_args(self, request, payment):
        return {
            'mandate_data': {
                'customer_acceptance': {
                    'type': 'online',
                    'online': {
                        'ip_address': get_client_ip(request),
                        'user_agent': request.META['HTTP_USER_AGENT'],
                    }
                },
            }
        }

    def checkout_prepare(self, request, cart):
        request.session['payment_stripe_sepa_debit_last4'] = request.POST.get('stripe_sepa_debit_last4', '')
        request.session['payment_stripe_sepa_debit_bank'] = request.POST.get('stripe_sepa_debit_bank', '')

        return super().checkout_prepare(request, cart)

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        try:
            return super().execute_payment(request, payment)
        finally:
            fields = ['accountname', 'line1', 'postal_code', 'city', 'country']
            for field in fields:
                if 'payment_stripe_sepa_debit_{}'.format(field) in request.session:
                    del request.session['payment_stripe_sepa_debit_{}'.format(field)]


class StripeAffirm(StripeMethod):
    identifier = 'stripe_affirm'
    verbose_name = _('Affirm via Stripe')
    public_name = _('Affirm')
    method = 'affirm'
    redirect_action_handling = 'redirect'

    def payment_is_valid_session(self, request):
        if 'payment_stripe_{}_payment_method_id'.format(self.method) in request.session:
            return True
        return False

    def checkout_prepare(self, request, cart):
        request.session['payment_stripe_{}_payment_method_id'.format(self.method)] = None
        return True

    def is_allowed(self, request: HttpRequest, total: Decimal=None) -> bool:
        return Decimal(50.00) <= total <= Decimal(30000.00) and super().is_allowed(request, total)

    def order_change_allowed(self, order: Order, request: HttpRequest=None) -> bool:
        return Decimal(50.00) <= order.pending_sum <= Decimal(30000.00) and super().order_change_allowed(order, request)

    def _intent_api_args(self, request, payment):
        return {
            'payment_method_data': {
                'type': 'affirm',
            }
        }

    def payment_form_render(self, request, total, order=None) -> str:
        template = get_template('plugins/stripe/simple_messaging_noform.html')
        ctx = {
            'request': request,
            'event': self.event,
            'total': self._decimal_to_int(total),
            'explanation': self.explanation,
            'method': self.method,
        }
        return template.render(ctx)


class StripeKlarna(Redirector):
    identifier = "stripe_klarna"
    verbose_name = _("Klarna via Stripe")
    public_name = _("Klarna")
    method = "klarna"
    allowed_countries = {"US", "CA", "AU", "NZ", "GB", "IE", "FR", "ES", "DE", "AT", "BE", "DK", "FI", "IT", "NL", "NO", "SE"}
    redirect_in_widget_allowed = False

    def _detect_country(self, request, order=None):
        def get_invoice_address():
            if order and getattr(order, 'invoice_address', None):
                request._checkout_flow_invoice_address = order.invoice_address
            if not hasattr(request, '_checkout_flow_invoice_address'):
                cs = cart_session(request)
                iapk = cs.get('invoice_address')
                if not iapk:
                    request._checkout_flow_invoice_address = InvoiceAddress()
                else:
                    try:
                        request._checkout_flow_invoice_address = InvoiceAddress.objects.get(pk=iapk, order__isnull=True)
                    except InvoiceAddress.DoesNotExist:
                        request._checkout_flow_invoice_address = InvoiceAddress()
            return request._checkout_flow_invoice_address

        ia = get_invoice_address()
        country = None
        if ia.country:
            country = str(ia.country)
        if country not in self.allowed_countries:
            if settings.HAS_GEOIP:
                g = GeoIP2()
                try:
                    res = g.country(get_client_ip(request))
                    if res['country_code'] and len(res['country_code']) == 2:
                        country = Country(res['country_code'])
                except AddressNotFoundError:
                    pass
            country = country or guess_country(self.event)
        if country not in self.allowed_countries:
            country = self.settings.merchant_country
        if country not in self.allowed_countries:
            country = "DE"
        return country

    def _intent_api_args(self, request, payment):
        return {
            "payment_method_data": {
                "type": "klarna",
                "billing_details": {
                    "email": payment.order.email,
                    "address": {
                        "country": self._detect_country(request, payment.order),
                    },
                },
            }
        }

    def payment_form_render(self, request, total, order=None) -> str:
        template = get_template(
            "plugins/stripe/simple_messaging_noform.html"
        )
        ctx = {
            "request": request,
            "event": self.event,
            "total": self._decimal_to_int(total),
            "method": self.method,
            'explanation': self.explanation,
            "country": self._detect_country(request, order)
        }
        return template.render(ctx)

    def test_mode_message(self):
        if self.settings.connect_client_id and not self.settings.secret_key:
            is_testmode = True
        else:
            is_testmode = (
                self.settings.secret_key and "_test_" in self.settings.secret_key
            )
        if is_testmode:
            return mark_safe(
                _(
                    "The Stripe plugin is operating in test mode. You can use one of <a {args}>many test "
                    "cards</a> to perform a transaction. No money will actually be transferred."
                ).format(
                    args='href="https://docs.klarna.com/resources/test-environment/sample-customer-data/" target="_blank"'
                )
            )
        return None
