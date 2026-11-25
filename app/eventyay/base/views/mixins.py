import json
from collections import OrderedDict
from contextlib import suppress
from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, QuerySet
from django.utils.functional import cached_property

from eventyay.base.forms.questions import (
    BaseInvoiceAddressForm,
    BaseInvoiceNameForm,
    BaseQuestionsForm,
)
from eventyay.base.models import (
    CartPosition,
    InvoiceAddress,
    OrderPosition,
    Question,
    QuestionAnswer,
    QuestionOption,
)
from eventyay.base.services.system_questions import (
    get_enabled_system_question_fields,
    get_system_question_base_states,
    get_system_question_product_overrides,
)
from eventyay.helpers.image_optimize import optimize_question_image
from eventyay.presale.signals import contact_form_fields_overrides


class BaseQuestionsViewMixin:
    form_class = BaseQuestionsForm
    all_optional = False

    @staticmethod
    def _keyfunc(pos):
        # Sort addons after the product they are an addon to
        if isinstance(pos, OrderPosition):
            i = pos.addon_to.positionid if pos.addon_to else pos.positionid
        else:
            i = pos.addon_to.pk if pos.addon_to else pos.pk
        addon_penalty = 1 if pos.addon_to else 0
        return i, addon_penalty, pos.pk

    @cached_property
    def _positions_for_questions(self):
        raise NotImplementedError()

    def get_question_override_sets(self, position):
        return []

    @cached_property
    def forms(self):
        """
        A list of forms with one form for each cart position that has questions
        the user can answer. All forms have a custom prefix, so that they can all be
        submitted at once.
        """
        formlist = []
        base_states = get_system_question_base_states(self.request.event)
        product_overrides = get_system_question_product_overrides(self.request.event)
        for cr in self._positions_for_questions:
            cartpos = cr if isinstance(cr, CartPosition) else None
            orderpos = cr if isinstance(cr, OrderPosition) else None
            form = self.form_class(
                event=self.request.event,
                prefix=cr.id,
                cartpos=cartpos,
                orderpos=orderpos,
                all_optional=self.all_optional,
                data=(self.request.POST if self.request.method == 'POST' else None),
                files=(self.request.FILES if self.request.method == 'POST' else None),
            )
            form.pos = cartpos or orderpos

            shared_system_fields = set()
            if form.pos.addon_to and form.pos.addon_to.product.admission and form.pos.product.admission:
                source_fields = get_enabled_system_question_fields(
                    self.request.event,
                    form.pos.addon_to.product,
                    base_states=base_states,
                    product_overrides=product_overrides,
                )
                target_fields = get_enabled_system_question_fields(
                    self.request.event,
                    form.pos.product,
                    base_states=base_states,
                    product_overrides=product_overrides,
                )
                shared_system_fields = source_fields & target_fields

            form.show_copy_answers_to_addon_button = bool(
                form.pos.addon_to
                and (
                    set(form.pos.addon_to.product.questions.all()) & set(form.pos.product.questions.all())
                    or shared_system_fields
                )
            )

            override_sets = self.get_question_override_sets(cr)
            for overrides in override_sets:
                for question_name, question_field in form.fields.items():
                    if hasattr(question_field, 'question'):
                        if question_field.question.identifier in overrides:
                            if 'initial' in overrides[question_field.question.identifier]:
                                question_field.initial = overrides[question_field.question.identifier]['initial']
                            if 'disabled' in overrides[question_field.question.identifier]:
                                question_field.disabled = overrides[question_field.question.identifier]['disabled']
                    else:
                        if question_name in overrides:
                            if 'initial' in overrides[question_name]:
                                question_field.initial = overrides[question_name]['initial']
                            if 'disabled' in overrides[question_name]:
                                question_field.disabled = overrides[question_name]['disabled']

            form.regular_fields = []
            form.badge_option_fields = []
            for field_name in form.fields:
                bound_field = form[field_name]
                if getattr(bound_field.field, 'badge_option', False):
                    form.badge_option_fields.append(bound_field)
                else:
                    form.regular_fields.append(bound_field)

            if len(form.fields) > 0:
                formlist.append(form)
        return formlist

    @cached_property
    def formdict(self):
        storage = OrderedDict()
        for f in self.forms:
            pos = f.pos
            if pos.addon_to_id:
                if pos.addon_to not in storage:
                    storage[pos.addon_to] = []
                storage[pos.addon_to].append(f)
            else:
                if pos not in storage:
                    storage[pos] = []
                storage[pos].append(f)

        groups = list(storage.values())
        if groups:
            first_group = groups[0]
            for i, group in enumerate(groups):
                if i == 0:
                    group[0].pos.show_copy_answers_main_button = False
                    continue

                group[0].pos.show_copy_answers_main_button = any(
                    set(form.fields.keys()) & set(first_group[addonidx].fields.keys())
                    for addonidx, form in enumerate(group) if addonidx < len(first_group)
                )

        return storage

    def is_valid(self):
        return all([f.is_valid() for f in self.forms])

    def questions_are_valid(self):
        return self.is_valid()

    def cleanup_staged_uploads(self):
        staged = getattr(self, '_staged_uploads', [])
        for storage, name in staged:
            with suppress(Exception):
                storage.delete(name)
        if hasattr(self, '_staged_uploads'):
            self._staged_uploads.clear()

    def save(self):
        failed = False
        if not self.is_valid():
            return False
        for form in self.forms:
            # Every form represents a CartPosition or OrderPosition with questions attached
            if not form.is_valid():
                failed = True
            else:
                if isinstance(form.pos, OrderPosition) and form.pos.pk:
                    form.pos.refresh_from_db()
                    fields_to_update = [k for k in form.changed_data if k in form.cleaned_data]
                else:
                    fields_to_update = list(form.cleaned_data.keys())

                meta_info = form.pos.meta_info_data
                for k in fields_to_update:
                    v = form.cleaned_data[k]
                    if k == 'attendee_name_parts':
                        form.pos.attendee_name_parts = v if v else None
                    elif k == 'attendee_email':
                        form.pos.attendee_email = v if v != '' else None
                    elif k == 'company':
                        form.pos.company = v if v != '' else None
                    elif k == 'job_title':
                        form.pos.job_title = v if v != '' else None
                    elif k == 'street':
                        form.pos.street = v if v != '' else None
                    elif k == 'zipcode':
                        form.pos.zipcode = v if v != '' else None
                    elif k == 'city':
                        form.pos.city = v if v != '' else None
                    elif k == 'country':
                        form.pos.country = v if v != '' else None
                    elif k == 'state':
                        form.pos.state = v if v != '' else None
                    elif k.startswith('question_'):
                        field = form.fields[k]
                        if hasattr(field, 'answer'):
                            # We already have a cached answer object, so we don't
                            # have to create a new one
                            if (
                                v == ''
                                or v is None
                                or (isinstance(field, forms.FileField) and v is False)
                                or (isinstance(v, QuerySet) and not v.exists())
                            ):
                                if field.answer.file:
                                    old_storage = field.answer.file.storage
                                    old_name = field.answer.file.name
                                    field.answer.file = None
                                    transaction.on_commit(
                                        lambda s=old_storage, n=old_name: s.delete(n)
                                    )
                                field.answer.delete()
                            else:
                                self._save_to_answer(field, field.answer, v)
                                field.answer.save()
                        elif v != '' and v is not None:
                            answer = QuestionAnswer(
                                cartposition=(form.pos if isinstance(form.pos, CartPosition) else None),
                                orderposition=(form.pos if isinstance(form.pos, OrderPosition) else None),
                                question=field.question,
                            )
                            try:
                                with transaction.atomic():
                                    self._save_to_answer(field, answer, v)
                                    answer.save()
                            except IntegrityError:
                                # Since we prefill ``field.answer`` at form creation time, there's a possible
                                #  race condition here if the users submits their save request a second time
                                # while the first one is still running, thus leading to duplicate QuestionAnswer
                                # objects. Since Django doesn't support UPSERT, the "proper" fix would be a transaction
                                # with select_for_update(), or at least fetching using get_or_create here again.
                                # However, both of these approaches have a significant performance overhead for
                                # *all* requests, while the issue happens very very rarely.
                                # So we opt for just catching the error and retrying properly.
                                answer = QuestionAnswer.objects.get(
                                    cartposition=(form.pos if isinstance(form.pos, CartPosition) else None),
                                    orderposition=(form.pos if isinstance(form.pos, OrderPosition) else None),
                                    question=field.question,
                                )
                                self._save_to_answer(field, answer, v)
                                answer.save()

                    else:
                        meta_info.setdefault('question_form_data', {})
                        if v is None:
                            if k in meta_info['question_form_data']:
                                del meta_info['question_form_data'][k]
                        else:
                            meta_info['question_form_data'][k] = v
                        if k == 'badge_hidden_fields' and isinstance(form.pos, OrderPosition):
                            from eventyay.plugins.badges.utils import (
                                get_badge_config_position,
                                invalidate_badge_cache_for_position,
                            )

                            invalidate_badge_cache_for_position(get_badge_config_position(form.pos))

                if fields_to_update:
                    form.pos.meta_info = json.dumps(meta_info)
                    form.pos.save()
        if hasattr(self, '_staged_uploads'):
            transaction.on_commit(lambda: getattr(self, '_staged_uploads', []).clear())
        return not failed

    def _save_to_answer(self, field, answer, value):
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ', '.join([str(o) for o in value])
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.answer = answstr
            answer.options.add(*value)
        elif isinstance(field, forms.ModelChoiceField):
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.options.add(value)
            answer.answer = value.answer
        elif isinstance(field, forms.FileField):
            if isinstance(value, UploadedFile):
                upload = optimize_question_image(value)
                old_file = answer.file
                old_storage = old_file.storage if old_file else None
                old_name = old_file.name if old_file else None
                answer.file.save(upload.name, upload)
                answer.answer = f'file://{answer.file.name}'
                if not hasattr(self, '_staged_uploads'):
                    self._staged_uploads = []
                self._staged_uploads.append((answer.file.storage, answer.file.name))
                if old_name and old_name != answer.file.name:
                    transaction.on_commit(
                        lambda s=old_storage, n=old_name: s.delete(n)
                    )
        else:
            answer.answer = value


class OrderQuestionsViewMixin(BaseQuestionsViewMixin):
    invoice_form_class = BaseInvoiceAddressForm
    invoice_name_form_class = BaseInvoiceNameForm
    only_user_visible = True
    all_optional = False

    @cached_property
    def _positions_for_questions(self):
        return self.positions

    @cached_property
    def positions(self):
        qqs = self.request.event.questions.all()
        if self.only_user_visible:
            qqs = qqs.filter(ask_during_checkin=False, hidden=False, active=True)
        return list(
            self.order.positions.select_related('product', 'variation').prefetch_related(
                Prefetch(
                    'answers',
                    QuestionAnswer.objects.prefetch_related('options'),
                    to_attr='answerlist',
                ),
                Prefetch(
                    'product__questions',
                    qqs.prefetch_related(
                        Prefetch(
                            'options',
                            QuestionOption.objects.prefetch_related(
                                Prefetch(
                                    # This prefetch statement is utter bullshit, but it actually prevents Django
                                    # from doing a lot of queries since ModelChoiceIterator stops trying to be
                                    # clever once we have a prefetch lookup on this query...
                                    'question',
                                    Question.objects.none(),
                                    to_attr='dummy',
                                )
                            ),
                        )
                    ).select_related('dependency_question'),
                    to_attr='questions_to_ask',
                ),
            )
        )

    @cached_property
    def invoice_address(self):
        try:
            return self.order.invoice_address
        except InvoiceAddress.DoesNotExist:
            return InvoiceAddress(order=self.order)

    @cached_property
    def address_asked(self):
        return self.request.event.settings.invoice_address_asked and (
            self.order.total != Decimal('0.00') or not self.request.event.settings.invoice_address_not_asked_free
        )

    @cached_property
    def _contact_override_sets(self):
        override_sets = [
            resp
            for recv, resp in contact_form_fields_overrides.send(
                self.request.event,
                request=self.request,
                order=self.order,
            )
        ]
        for override in override_sets:
            for k in override:
                # We don't want initial values to be modified, they should come from the order directly
                override[k].pop('initial', None)
        return override_sets

    @cached_property
    def invoice_form(self):
        if not self.address_asked and self.request.event.settings.invoice_name_required:
            f = self.invoice_name_form_class(
                data=self.request.POST if self.request.method == 'POST' else None,
                event=self.request.event,
                instance=self.invoice_address,
                validate_vat_id=False,
                all_optional=self.all_optional,
            )
        elif self.address_asked:
            f = self.invoice_form_class(
                data=self.request.POST if self.request.method == 'POST' else None,
                event=self.request.event,
                instance=self.invoice_address,
                validate_vat_id=False,
                all_optional=self.all_optional,
            )
        else:
            f = forms.Form(data=self.request.POST if self.request.method == 'POST' else None)

        override_sets = self._contact_override_sets
        for overrides in override_sets:
            for fname, val in overrides.items():
                if 'disabled' in val and fname in f.fields:
                    f.fields[fname].disabled = val['disabled']

        return f

    @staticmethod
    def _is_invoice_order_unique_violation(err):
        cause = getattr(err, '__cause__', None)
        diag = getattr(cause, 'diag', None)
        if diag is not None:
            return getattr(diag, 'constraint_name', None) == 'base_invoiceaddress_order_id_key'

        err_msg = str(err).lower().replace('"', '').replace('`', '')
        return err_msg.strip() == 'unique constraint failed: base_invoiceaddress.order_id'

    def save_invoice_form(self):
        if not hasattr(self.invoice_form, 'save'):
            return

        def _apply_and_save(target):
            self.invoice_form.instance = target
            self.__dict__['invoice_address'] = target
            with suppress(Exception):
                self.order.invoice_address = target
            if self.invoice_form.has_changed():
                for k in self.invoice_form.changed_data:
                    if k in self.invoice_form.cleaned_data:
                        setattr(target, k, self.invoice_form.cleaned_data[k])
                target.save()

        instance = getattr(self.invoice_form, 'instance', None)
        if instance and instance.pk:
            if self.invoice_form.has_changed():
                instance.refresh_from_db()
                _apply_and_save(instance)
        else:
            existing = InvoiceAddress.objects.filter(order=self.order).first()
            if existing:
                _apply_and_save(existing)
            else:
                try:
                    with transaction.atomic():
                        self.invoice_form.save()
                        self.__dict__['invoice_address'] = self.invoice_form.instance
                        with suppress(Exception):
                            self.order.invoice_address = self.invoice_form.instance
                except IntegrityError as err:
                    if not self._is_invoice_order_unique_violation(err):
                        raise
                    existing = InvoiceAddress.objects.filter(order=self.order).first()
                    if not existing:
                        raise
                    _apply_and_save(existing)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['formgroups'] = self.formdict.items()
        ctx['invoice_form'] = self.invoice_form
        ctx['invoice_address_asked'] = self.address_asked
        return ctx
