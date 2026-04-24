from decimal import Decimal
from http import HTTPMethod
from typing import cast

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from eventyay.base.models import Event, TaxRule, User
from eventyay.base.services.cart import update_tax_rates
from eventyay.base.services.system_questions import (
    get_system_question_asked_required,
    get_system_question_base_states,
    get_system_question_product_overrides,
)
from eventyay.presale.checkoutflowstep.template_flow_step import TemplateFlowStep
from eventyay.presale.forms.checkout import (
    ContactForm,
    InvoiceAddressForm,
    InvoiceNameForm,
)
from eventyay.presale.signals import (
    checkout_all_optional,
    contact_form_fields_overrides,
    question_form_fields,
    question_form_fields_overrides,
)
from eventyay.presale.views import CartMixin, get_cart_is_free
from eventyay.presale.views.cart import get_or_create_cart_id
from eventyay.presale.views.questions import QuestionsViewMixin


class QuestionsStep(QuestionsViewMixin, CartMixin, TemplateFlowStep):
    priority = 50
    identifier = 'questions'
    template_name = 'pretixpresale/event/checkout_questions.html'
    label = pgettext_lazy('checkoutflow', 'Your information')

    def is_applicable(self, request):
        return True

    @cached_property
    def all_optional(self):
        for recv, resp in checkout_all_optional.send(sender=self.request.event, request=self.request):
            if resp:
                return True
        return False

    @cached_property
    def _contact_override_sets(self):
        return [
            resp
            for recv, resp in contact_form_fields_overrides.send(
                self.request.event,
                request=self.request,
                order=None,
            )
        ]

    @cached_property
    def contact_form(self):
        wd = self.cart_session.get('widget_data', {})
        user = cast(User, self.request.user)
        initial = {
            'email': (
                (user.primary_email if user.is_authenticated else '')
                or self.cart_session.get('email', '')
                or wd.get('email', '')
            ),
            'phone': wd.get('phone', None),
        }
        initial.update(self.cart_session.get('contact_form_data', {}))

        override_sets = self._contact_override_sets
        for overrides in override_sets:
            initial.update({k: v['initial'] for k, v in overrides.items() if 'initial' in v})

        f = ContactForm(
            data=self.request.POST if self.request.method == HTTPMethod.POST else None,
            event=self.request.event,
            request=self.request,
            initial=initial,
            all_optional=self.all_optional,
        )
        if 'email' in f.fields and wd.get('email', '') and wd.get('fix', '') == 'true':
            f.fields['email'].disabled = True

        for overrides in override_sets:
            for fname, val in overrides.items():
                if 'disabled' in val and fname in f.fields:
                    f.fields[fname].disabled = val['disabled']

        return f

    def get_question_override_sets(self, cart_position):
        return [
            resp
            for recv, resp in question_form_fields_overrides.send(
                self.request.event, position=cart_position, request=self.request
            )
        ]

    @cached_property
    def eu_reverse_charge_relevant(self):
        return any(
            [
                p.product.tax_rule and (p.product.tax_rule.eu_reverse_charge or p.product.tax_rule.custom_rules)
                for p in self.positions
            ]
        )

    @cached_property
    def invoice_form(self):
        wd = self.cart_session.get('widget_data', {})
        if not self.invoice_address.pk:
            wd_initial = {
                'name_parts': {
                    k[21:].replace('-', '_'): v for k, v in wd.items() if k.startswith('invoice-address-name-')
                },
                'company': wd.get('invoice-address-company', ''),
                'is_business': bool(wd.get('invoice-address-company', '')),
                'street': wd.get('invoice-address-street', ''),
                'zipcode': wd.get('invoice-address-zipcode', ''),
                'city': wd.get('invoice-address-city', ''),
                'country': wd.get('invoice-address-country', ''),
            }
        else:
            wd_initial = {}
        initial = dict(wd_initial)

        override_sets = self._contact_override_sets
        for overrides in override_sets:
            initial.update({k: v['initial'] for k, v in overrides.items() if 'initial' in v})

        if not self.address_asked and self.request.event.settings.invoice_name_required:
            f = InvoiceNameForm(
                data=self.request.POST if self.request.method == HTTPMethod.POST else None,
                event=self.request.event,
                request=self.request,
                instance=self.invoice_address,
                initial=initial,
                validate_vat_id=False,
                all_optional=self.all_optional,
            )
        else:
            f = InvoiceAddressForm(
                data=self.request.POST if self.request.method == HTTPMethod.POST else None,
                event=self.request.event,
                request=self.request,
                initial=initial,
                instance=self.invoice_address,
                validate_vat_id=self.eu_reverse_charge_relevant,
                all_optional=self.all_optional,
            )
        for name, field in f.fields.items():
            if wd_initial.get(name) and wd.get('fix', '') == 'true':
                field.disabled = True

        for overrides in override_sets:
            for fname, val in overrides.items():
                if 'disabled' in val and fname in f.fields:
                    f.fields[fname].disabled = val['disabled']

        return f

    @cached_property
    def address_asked(self):
        return self.request.event.settings.invoice_address_asked and (
            not self.request.event.settings.invoice_address_not_asked_free or not get_cart_is_free(self.request)
        )

    def post(self, request):
        self.request = request
        failed = not self.save() or not self.contact_form.is_valid()
        if self.address_asked or self.request.event.settings.invoice_name_required:
            failed = failed or not self.invoice_form.is_valid()
        if failed:
            messages.error(
                request,
                _('We had difficulties processing your input. Please review the errors below.'),
            )
            return self.render()
        if 'email' in self.contact_form.cleaned_data:
            self.cart_session['email'] = self.contact_form.cleaned_data['email']
        else:
            self.cart_session.pop('email', None)
        d = dict(self.contact_form.cleaned_data)
        if d.get('phone'):
            d['phone'] = str(d['phone'])
        self.cart_session['contact_form_data'] = d
        if self.address_asked or self.request.event.settings.invoice_name_required:
            addr = self.invoice_form.save()
            try:
                diff = update_tax_rates(
                    event=request.event,
                    cart_id=get_or_create_cart_id(request),
                    invoice_address=addr,
                )
            except TaxRule.SaleNotAllowed:
                messages.error(
                    request,
                    _(
                        "Unfortunately, based on the invoice address you entered, we're not able to sell you "
                        'the selected products for tax-related legal reasons.'
                    ),
                )
                return self.render()

            self.cart_session['invoice_address'] = addr.pk
            if abs(diff) > Decimal('0.001'):
                messages.info(
                    request,
                    _(
                        'Due to the invoice address you entered, we need to apply a different tax '
                        'rate to your purchase and the price of the products in your cart has '
                        'changed accordingly.'
                    ),
                )
                return redirect(self.get_next_url(request) + '?open_cart=true')

        return redirect(self.get_next_url(request))

    def is_completed(self, request, warn=False):
        self.request = request
        event = cast(Event, request.event)
        if event.settings.order_email_asked:
            try:
                emailval = EmailValidator()
                if event.settings.order_email_required and not self.cart_session.get('email') and not self.all_optional:
                    if warn:
                        messages.warning(request, _('Please enter a valid email address.'))
                    return False
                if self.cart_session.get('email'):
                    emailval(self.cart_session.get('email'))
            except ValidationError:
                if warn:
                    messages.warning(request, _('Please enter a valid email address.'))
                return False

        if not self.all_optional:
            if self.address_asked:
                if event.settings.invoice_address_required and (
                    not self.invoice_address or not self.invoice_address.street
                ):
                    messages.warning(request, _('Please enter your invoicing address.'))
                    return False

            if request.event.settings.invoice_name_required and (
                not self.invoice_address or not self.invoice_address.name
            ):
                messages.warning(request, _('Please enter your name.'))
                return False

        base_states = get_system_question_base_states(self.request.event)
        product_overrides = get_system_question_product_overrides(self.request.event)

        for cp in self._positions_for_questions:
            answ = {aw.question_id: aw for aw in cp.answerlist}
            question_cache = {q.pk: q for q in cp.product.questions_to_ask}

            def question_is_visible(parentid, qvals):
                if parentid not in question_cache:
                    return False
                parentq = question_cache[parentid]
                if parentq.dependency_question_id and not question_is_visible(
                    parentq.dependency_question_id, parentq.dependency_values
                ):
                    return False
                if parentid not in answ:
                    return False
                return (
                    ('True' in qvals and answ[parentid].answer == 'True')
                    or ('False' in qvals and answ[parentid].answer == 'False')
                    or (any(qval in [o.identifier for o in answ[parentid].options.all()] for qval in qvals))
                )

            def question_is_required(q):
                return q.required and (
                    not q.dependency_question_id or question_is_visible(q.dependency_question_id, q.dependency_values)
                )

            for q in cp.product.questions_to_ask:
                if question_is_required(q) and q.id not in answ:
                    if warn:
                        messages.warning(
                            request,
                            _('Please fill in answers to all required questions.'),
                        )
                    return False

            _, attendee_name_required = get_system_question_asked_required(
                self.request.event,
                'attendee_name_parts',
                cp.product,
                base_states=base_states,
                product_overrides=product_overrides,
            )
            _, attendee_email_required = get_system_question_asked_required(
                self.request.event,
                'attendee_email',
                cp.product,
                base_states=base_states,
                product_overrides=product_overrides,
            )
            _, attendee_company_required = get_system_question_asked_required(
                self.request.event,
                'company',
                cp.product,
                base_states=base_states,
                product_overrides=product_overrides,
            )
            _, attendee_job_title_required = get_system_question_asked_required(
                self.request.event,
                'job_title',
                cp.product,
                base_states=base_states,
                product_overrides=product_overrides,
            )
            _, attendee_address_required = get_system_question_asked_required(
                self.request.event,
                'street',
                cp.product,
                base_states=base_states,
                product_overrides=product_overrides,
            )

            if (
                cp.product.admission
                and attendee_name_required
                and not cp.attendee_name_parts
            ):
                if warn:
                    messages.warning(request, _('Please fill in answers to all required questions.'))
                return False
            if (
                cp.product.admission
                and attendee_email_required
                and not cp.attendee_email
            ):
                if warn:
                    messages.warning(request, _('Please fill in answers to all required questions.'))
                return False
            if (
                cp.product.admission
                and attendee_company_required
                and not cp.company
            ):
                if warn:
                    messages.warning(request, _('Please fill in answers to all required questions.'))
                return False
            if (
                cp.product.admission
                and attendee_job_title_required
                and not cp.job_title
            ):
                if warn:
                    messages.warning(request, _('Please fill in answers to all required questions.'))
                return False
            if (
                cp.product.admission
                and attendee_address_required
                and (not cp.street or not cp.city or not cp.country)
            ):
                if warn:
                    messages.warning(request, _('Please fill in answers to all required questions.'))
                return False

            responses = question_form_fields.send(sender=event, position=cp)
            form_data = cp.meta_info_data.get('question_form_data', {})
            for r, response in sorted(responses, key=lambda r: str(r[0])):
                for key, value in response.items():
                    if value.required and not form_data.get(key):
                        return False
        return True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['formgroups'] = self.formdict.items()
        ctx['contact_form'] = self.contact_form
        ctx['invoice_form'] = self.invoice_form
        ctx['reverse_charge_relevant'] = self.eu_reverse_charge_relevant
        ctx['cart'] = self.get_cart()
        ctx['cart_session'] = self.cart_session
        ctx['invoice_address_asked'] = self.address_asked
        return ctx
