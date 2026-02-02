from collections import OrderedDict
from typing import List, Union

from django import forms
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput

from eventyay.base.forms import SecretKeySettingsField, SettingsForm
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.signals import register_global_settings


class GlobalSettingsForm(SettingsForm):
    auto_fields = ['region', 'mail_from']

    def _setting_default(self):
        """
        Load default email setting form .cfg file if not set
        """
        global_settings = self.obj.settings
        if global_settings.get('billing_validation') is None:
            global_settings.set('billing_validation', True)
        if global_settings.get('smtp_port') is None or global_settings.get('smtp_port') == '':
            self.obj.settings.set('smtp_port', settings.EMAIL_PORT)
        if global_settings.get('smtp_host') is None or global_settings.get('smtp_host') == '':
            self.obj.settings.set('smtp_host', settings.EMAIL_HOST)
        if global_settings.get('smtp_username') is None or global_settings.get('smtp_username') == '':
            self.obj.settings.set('smtp_username', settings.EMAIL_HOST_USER)
        if global_settings.get('smtp_password') is None or global_settings.get('smtp_password') == '':
            self.obj.settings.set('smtp_password', settings.EMAIL_HOST_PASSWORD)
        if global_settings.get('smtp_use_tls') is None or global_settings.get('smtp_use_tls') == '':
            self.obj.settings.set('smtp_use_tls', settings.EMAIL_USE_TLS)
        if global_settings.get('smtp_use_ssl') is None or global_settings.get('smtp_use_ssl') == '':
            self.obj.settings.set('smtp_use_ssl', settings.EMAIL_USE_SSL)
        if global_settings.get('email_vendor') is None or global_settings.get('email_vendor') == '':
            self.obj.settings.set('email_vendor', 'smtp')

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        self._setting_default()
        super().__init__(*args, obj=self.obj, **kwargs)

        smtp_select = [('sendgrid', _('SendGrid')), ('smtp', _('SMTP'))]

        self.fields = OrderedDict(
            list(self.fields.items())
            + [
                (
                    'billing_validation',
                    forms.BooleanField(
                        required=False,
                        label=_('Billing validation'),
                        help_text=_(
                            'Billing validation lets you require organizers to set up a billing method before they can create events. '
                            'When this option is enabled, no new event can be created until a valid billing method has been added.'
                        ),
                    ),
                ),
                (
                    'footer_text',
                    I18nFormField(
                        widget=I18nTextInput,
                        required=False,
                        label=_('Additional footer text'),
                        help_text=_('Will be included as additional text in the footer, site-wide.'),
                    ),
                ),
                (
                    'footer_link',
                    I18nFormField(
                        widget=I18nTextInput,
                        required=False,
                        label=_('Additional footer link'),
                        help_text=_('Will be included as the link in the additional footer text.'),
                    ),
                ),
                (
                    'banner_message',
                    I18nFormField(
                        widget=I18nTextarea,
                        required=False,
                        label=_('Global message banner'),
                    ),
                ),
                (
                    'banner_message_detail',
                    I18nFormField(
                        widget=I18nTextarea,
                        required=False,
                        label=_('Global message banner detail text'),
                    ),
                ),
                (
                    'opencagedata_apikey',
                    SecretKeySettingsField(
                        required=False,
                        label=_('OpenCage API key for geocoding'),
                    ),
                ),
                (
                    'mapquest_apikey',
                    SecretKeySettingsField(
                        required=False,
                        label=_('MapQuest API key for geocoding'),
                    ),
                ),
                (
                    'leaflet_tiles',
                    forms.CharField(
                        required=False,
                        label=_('Leaflet tiles URL pattern'),
                        help_text=_('e.g. {sample}').format(sample='https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'),
                    ),
                ),
                (
                    'leaflet_tiles_attribution',
                    forms.CharField(
                        required=False,
                        label=_('Leaflet tiles attribution'),
                        help_text=_('e.g. {sample}').format(
                            sample='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        ),
                    ),
                ),
                (
                    'email_vendor',
                    forms.ChoiceField(
                        label=_('System Email'),
                        required=True,
                        widget=forms.RadioSelect,
                        choices=smtp_select,
                    ),
                ),
                (
                    'send_grid_api_key',
                    forms.CharField(
                        required=False,
                        label=_('Sendgrid Token'),
                        widget=forms.TextInput(attrs={'placeholder': 'SG.xxxxxxxx'}),
                    ),
                ),
                (
                    'smtp_host',
                    forms.CharField(
                        label=_('Hostname'),
                        required=False,
                        widget=forms.TextInput(attrs={'placeholder': 'mail.example.org'}),
                    ),
                ),
                (
                    'smtp_port',
                    forms.IntegerField(
                        label=_('Port'),
                        required=False,
                        widget=forms.TextInput(attrs={'placeholder': 'e.g. 587, 465, 25, ...'}),
                    ),
                ),
                (
                    'smtp_username',
                    forms.CharField(
                        label=_('Username'),
                        widget=forms.TextInput(attrs={'placeholder': 'myuser@example.org'}),
                        required=False,
                    ),
                ),
                (
                    'smtp_password',
                    forms.CharField(
                        label=_('Password'),
                        required=False,
                        widget=forms.PasswordInput(
                            attrs={
                                'autocomplete': 'new-password'  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
                            }
                        ),
                    ),
                ),
                (
                    'smtp_use_tls',
                    forms.BooleanField(
                        label=_('Use STARTTLS'),
                        help_text=_('Commonly enabled on port 587.'),
                        required=False,
                    ),
                ),
                (
                    'smtp_use_ssl',
                    forms.BooleanField(
                        label=_('Use SSL'),
                        help_text=_('Commonly enabled on port 465.'),
                        required=False,
                    ),
                ),
            ]
        )
        responses = register_global_settings.send(self)
        for r, response in sorted(responses, key=lambda r: str(r[0])):
            for key, value in response.items():
                # We need to be this explicit, since OrderedDict.update does not retain ordering
                self.fields[key] = value

        self.fields['banner_message'].widget.attrs['rows'] = '2'
        self.fields['banner_message_detail'].widget.attrs['rows'] = '3'
        self.fields = OrderedDict(
            list(self.fields.items())
            + [
                # Stripe for organizer billing
                (
                    'payment_stripe_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_live_'),),
                        help_text=_('Live publishable key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_live_', 'rk_live_']),),
                        help_text=_('Live secret key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_test_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_test_'),),
                        help_text=_('Test publishable key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'payment_stripe_test_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_test_', 'rk_test_']),),
                        help_text=_('Test secret key for organizer billing and platform fees.'),
                    ),
                ),
                (
                    'stripe_webhook_secret_key',
                    SecretKeySettingsField(
                        label=_('Webhook secret key'),
                        required=False,
                        help_text=_('Configure this endpoint in your Stripe dashboard to receive billing events.'),
                    ),
                ),
                # Stripe for ticket payments
                (
                    'payment_stripe_connect_client_id',
                    forms.CharField(
                        label=_('Client ID'),
                        required=False,
                        help_text=_('Stripe Connect client ID for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_live_'),),
                        help_text=_('Live publishable key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Live)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_live_', 'rk_live_']),),
                        help_text=_('Live secret key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_test_publishable_key',
                    forms.CharField(
                        label=_('Publishable key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator('pk_test_'),),
                        help_text=_('Test publishable key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_test_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key (Test)'),
                        required=False,
                        validators=(StripeKeyValidator(['sk_test_', 'rk_test_']),),
                        help_text=_('Test secret key for ticket payments via the Stripe plugin.'),
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_percent',
                    forms.DecimalField(
                        label=_('App fee percentage'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Percentage fee charged on ticket payments.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_min',
                    forms.DecimalField(
                        label=_('App fee minimum'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Minimum fee amount charged on ticket payments.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                (
                    'payment_stripe_connect_app_fee_max',
                    forms.DecimalField(
                        label=_('App fee maximum'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('Maximum fee amount charged on ticket payments.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                # PayPal
                (
                    'payment_paypal_connect_client_id',
                    forms.CharField(
                        label=_('Client ID'),
                        required=False,
                        help_text=_('PayPal Connect client ID for payment processing.'),
                    ),
                ),
                (
                    'payment_paypal_connect_secret_key',
                    SecretKeySettingsField(
                        label=_('Secret key'),
                        required=False,
                        help_text=_('PayPal Connect secret key for payment processing.'),
                    ),
                ),
                (
                    'payment_paypal_connect_endpoint',
                    forms.CharField(
                        label=_('API Endpoint'),
                        required=False,
                        help_text=_('PayPal API endpoint (e.g., https://api.paypal.com or https://api.sandbox.paypal.com).'),
                    ),
                ),
                (
                    'ticket_fee_percentage',
                    forms.DecimalField(
                        label=_('Ticket fee percentage'),
                        required=False,
                        decimal_places=2,
                        max_digits=10,
                        help_text=_('A percentage fee will be charged for each ticket sold.'),
                        validators=[MinValueValidator(0)],
                    ),
                ),
                (
                    'allow_all_users_create_organizer',
                    forms.BooleanField(
                        label=_('All registered users can create organizers'),
                        help_text=_('If enabled, all registered users will be allowed to create organizers. System admins can always create organizers.'),
                        required=False,
                    ),
                ),
                (
                    'allow_payment_users_create_organizer',
                    forms.BooleanField(
                        label=_('All accounts with payment information can create organizers'),
                        help_text=_('If enabled, users with valid payment information on file will be allowed to create organizers. System admins can always create organizers.'),
                        required=False,
                    ),
                ),
            ]
        )

        self.field_groups = [
            ('basics', _('Basics'), [
                'footer_text', 'footer_link', 'banner_message', 'banner_message_detail',
            ]),
            ('localization', _('Localization'), [
                'region',
            ]),
            ('email', _('Email'), [
                'mail_from', 'email_vendor', 'send_grid_api_key',
                'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl',
            ]),
            ('payment_gateways', _('Payment Gateways'), [
                # Stripe for Organizer Billing
                'payment_stripe_publishable_key',
                'payment_stripe_secret_key',
                'payment_stripe_test_publishable_key',
                'payment_stripe_test_secret_key',
                'stripe_webhook_secret_key',

                # Stripe for Ticket Payments
                'payment_stripe_connect_client_id',
                'payment_stripe_connect_publishable_key',
                'payment_stripe_connect_secret_key',
                'payment_stripe_connect_test_publishable_key',
                'payment_stripe_connect_test_secret_key',
                'payment_stripe_connect_app_fee_percent',
                'payment_stripe_connect_app_fee_min',
                'payment_stripe_connect_app_fee_max',

                # PayPal
                'payment_paypal_connect_client_id',
                'payment_paypal_connect_secret_key',
                'payment_paypal_connect_endpoint',
            ]),
            ('ticket_fee', _('Ticket fee'), [
                'ticket_fee_percentage',
            ]),
            ('billing_validation', _('Billing validation'), [
                'billing_validation',
            ]),
            ('maps', _('Maps'), [
                'opencagedata_apikey', 'mapquest_apikey', 'leaflet_tiles', 'leaflet_tiles_attribution',
            ]),
            ('organizers', _('Organizers'), [
                'allow_all_users_create_organizer',
                'allow_payment_users_create_organizer',
            ]),
        ]

    def clean(self):
        data = super().clean()

        # Validate SendGrid token is provided when SendGrid is selected
        if data.get('email_vendor') == 'sendgrid':
            if not data.get('send_grid_api_key'):
                raise forms.ValidationError({'send_grid_api_key': _('This field is required when using SendGrid as email vendor.')})

        return data


class UpdateSettingsForm(SettingsForm):
    update_check_perform = forms.BooleanField(
        required=False,
        label=_('Perform update checks'),
        help_text=_(
            'During the update check, eventyay will report an anonymous, unique installation ID, '
            'the current version of the system and your installed plugins and the number of active and '
            'inactive events in your installation to servers operated by the eventyay developers. We '
            'will only store anonymous data, never any IP addresses and we will not know who you are '
            'or where to find your instance. You can disable this behavior here at any time.'
        ),
    )
    update_check_email = forms.EmailField(
        required=False,
        label=_('E-mail notifications'),
        help_text=_(
            'We will notify you at this address if we detect that a new update is available. This '
            'address will not be transmitted to eventyay.com, the emails will be sent by this server '
            'locally.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        super().__init__(*args, obj=self.obj, **kwargs)


class SSOConfigForm(SettingsForm):
    redirect_url = forms.URLField(
        required=True,
        label=_('Redirect URL'),
        help_text=_('e.g. {sample}').format(sample='https://app-test.eventyay.com/talk/oauth2/callback/'),
    )

    def __init__(self, *args, **kwargs):
        self.obj = GlobalSettingsObject()
        super().__init__(*args, obj=self.obj, **kwargs)


class StripeKeyValidator:
    """
    Validates that a given Stripe key starts with the expected prefix(es).

    This validator ensures that Stripe API keys conform to the expected format
    by checking their prefixes. It supports both single prefix validation and
    multiple prefix validation.
    """

    def __init__(self, prefix: Union[str, List[str]]) -> None:
        if not prefix:
            raise ValueError('Prefix cannot be empty')

        if isinstance(prefix, list):
            if not all(isinstance(p, str) and p for p in prefix):
                raise ValueError('All prefixes must be non-empty strings')
            self._prefixes = prefix
        elif isinstance(prefix, str):
            if not prefix.strip():
                raise ValueError('Prefix cannot be whitespace')
            self._prefixes = [prefix]

    def __call__(self, value: str) -> None:
        if not value:
            raise forms.ValidationError(_('The Stripe key cannot be empty.'), code='invalid-stripe-key')

        if not any(value.startswith(p) for p in self._prefixes):
            if len(self._prefixes) == 1:
                message = _('The provided key does not look valid. It should start with "%(prefix)s".')
                params = {'value': value, 'prefix': self._prefixes[0]}
            else:
                message = _('The provided key does not look valid. It should start with one of: %(prefixes)s')
                params = {
                    'value': value,
                    'prefixes': ', '.join(f'"{p}"' for p in self._prefixes),
                }

            raise forms.ValidationError(message, code='invalid-stripe-key', params=params)
