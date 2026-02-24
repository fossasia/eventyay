import logging
from itertools import chain

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE

from eventyay.base.forms.questions import (
    BaseInvoiceAddressForm,
    BaseQuestionsForm,
    WrappedPhoneNumberPrefixWidget,
    guess_country,
)
from eventyay.base.i18n import get_babel_locale, language
from eventyay.base.models import Event
from eventyay.base.validators import EmailBanlistValidator
from eventyay.presale.signals import contact_form_fields

logger = logging.getLogger(__name__)


class ContactForm(forms.Form):
    required_css_class = 'required'
    # This field will be dropped depending on `include_wikimedia_username` event setting.
    wikimedia_username = forms.CharField(
        label=_('Wikimedia Username'),
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
    )
    phone = PhoneNumberField(
        label=_('Phone number'),
        required=False,
        help_text='',
        widget=WrappedPhoneNumberPrefixWidget(),
    )

    def __init__(self, *args, event: Event, request: HttpRequest, all_optional=False, **kwargs):
        self.event = event
        self.request = request
        self.all_optional = all_optional
        super().__init__(*args, **kwargs)

        if event.settings.order_email_asked:
            email_required = event.settings.order_email_required and not self.all_optional
            self.fields['email'] = forms.EmailField(
                label=_('E-mail'),
                required=email_required,
                validators=[EmailBanlistValidator()],
                widget=forms.EmailInput(attrs={'autocomplete': 'section-contact email'}),
            )
            if not request.session.get('iframe_session', False):
                # There is a browser quirk in Chrome that leads to incorrect initial scrolling in iframes if there
                # is an autofocus field. Who would have thought… See e.g. here:
                # https://floatboxjs.com/forum/topic.php?post=8440&usebb_sid=2e116486a9ec6b7070e045aea8cded5b#post8440
                self.fields['email'].widget.attrs['autofocus'] = 'autofocus'
            self.fields['email'].help_text = event.settings.checkout_email_helptext
            self.fields['email'].widget.attrs['placeholder'] = 'Valid email address'

        if event.settings.order_email_asked and event.settings.order_email_asked_twice:
            self.fields['email_repeat'] = forms.EmailField(
                label=_('E-mail address (repeated)'),
                help_text=_('Please enter the same email address again to make sure you typed it correctly.'),
            )

        if event.settings.order_phone_asked:
            self.fields['phone'].required = event.settings.order_phone_required and not self.all_optional
            self.fields['phone'].help_text = event.settings.checkout_phone_helptext
            with language(get_babel_locale()):
                default_country = guess_country(event)
                default_prefix = None
                phone_initial = ''
                for prefix, values in _COUNTRY_CODE_TO_REGION_CODE.items():
                    if str(default_country) in values:
                        default_prefix = prefix
                        break
                if passed_initial := self.initial.get('phone'):
                    try:
                        phone_number = PhoneNumber().from_string(passed_initial)
                        phone_initial = str(phone_number)
                    except NumberParseException:
                        pass
                elif default_prefix:
                    phone_initial = f'+{default_prefix}.'
            self.fields['phone'].initial = phone_initial
        else:
            del self.fields['phone']

        # Wikimedia username field visibility based on event setting
        if not event.settings.include_wikimedia_username:
            logger.debug('Dropping wikimedia_username field because `include_wikimedia_username` setting is False.')
            self.fields.pop('wikimedia_username', None)
        else:
            # Configure read-only Wikimedia username initial without redefining the field
            wm_initial = (
                self.initial.get('wikimedia_username')
                or getattr(getattr(request, 'user', None), 'wikimedia_username', None)
                or request.session.get('wikimedia_username')
            )
            if wm_initial:
                self.fields['wikimedia_username'].initial = wm_initial

        responses = contact_form_fields.send(event, request=request)
        for r, response in responses:
            for key, value in response.items():
                # We need to be this explicit, since OrderedDict.update does not retain ordering
                self.fields[key] = value
        if self.all_optional:
            for k, v in self.fields.items():
                v.required = False
                v.widget.is_required = False

    def clean(self):
        if (
            self.event.settings.order_email_asked
            and self.event.settings.order_email_asked_twice
            and self.cleaned_data.get('email')
            and self.cleaned_data.get('email_repeat')
        ):
            if self.cleaned_data.get('email').lower() != self.cleaned_data.get('email_repeat').lower():
                raise ValidationError(_('Please enter the same email address twice.'))


class InvoiceAddressForm(BaseInvoiceAddressForm):
    required_css_class = 'required'
    vat_warning = True


class InvoiceNameForm(InvoiceAddressForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in list(self.fields.keys()):
            if f != 'name_parts':
                del self.fields[f]


class QuestionsForm(BaseQuestionsForm):
    """
    This form class is responsible for asking order-related questions. This includes
    the attendee name for admission tickets, if the corresponding setting is enabled,
    as well as additional questions defined by the organizer.
    """

    required_css_class = 'required'


class AddOnRadioSelect(forms.RadioSelect):
    option_template_name = 'pretixpresale/forms/addon_choice_option.html'

    def optgroups(self, name, value, attrs=None):
        attrs = attrs or {}
        groups = []
        has_selected = False
        for index, (option_value, option_label, option_desc) in enumerate(chain(self.choices)):
            if option_value is None:
                option_value = ''
            if isinstance(option_label, (list, tuple)):
                raise TypeError('Choice groups are not supported here')
            group_name = None
            subgroup = []
            groups.append((group_name, subgroup, index))

            selected = force_str(option_value) in value and (has_selected is False or self.allow_multiple_selected)
            if selected is True and has_selected is False:
                has_selected = True
            attrs['description'] = option_desc
            subgroup.append(
                self.create_option(
                    name,
                    option_value,
                    option_label,
                    selected,
                    index,
                    subindex=None,
                    attrs=attrs,
                )
            )

        return groups


class AddOnVariationField(forms.ChoiceField):
    def valid_value(self, value):
        text_value = force_str(value)
        for k, v, d in self.choices:
            if value == k or text_value == force_str(k):
                return True
        return False
