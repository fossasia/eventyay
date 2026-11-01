import io
from urllib.parse import quote_plus

from defusedcsv import csv
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F, Min, Q, Subquery, Sum
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    UpdateView,
    View,
)

from eventyay.base.models import CartPosition, LogEntry, Quota, Voucher
from eventyay.base.models.vouchers import _generate_random_code
from eventyay.base.services.locking import NoLockManager
from eventyay.base.services.vouchers import vouchers_send
from eventyay.base.views.tasks import AsyncFormView
from eventyay.control.forms.filter import VoucherFilterForm, advanced_filter_count, advanced_filters_open_from_get
from eventyay.control.forms.vouchers import VoucherBulkForm, VoucherForm, VoucherGroupForm
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.signals import voucher_form_class
from eventyay.control.views import PaginationMixin
from eventyay.helpers.models import modelcopy
from eventyay.multidomain.urlreverse import build_absolute_uri


class VoucherList(PaginationMixin, EventPermissionRequiredMixin, ListView):
    model = Voucher
    context_object_name = 'vouchers'
    template_name = 'pretixcontrol/vouchers/index.html'
    permission = 'can_view_vouchers'

    def get_filtered_queryset(self):
        qs = self.request.event.vouchers.filter(waitinglistentries__isnull=True).select_related(
            'product', 'variation', 'seat', 'quota', 'subevent'
        ).prefetch_related('limit_products', 'limit_variations', 'limit_variations__product')
        if self.filter_form and self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        return qs.distinct()

    def get_queryset(self):
        qs = self.get_filtered_queryset()
        group_representatives = (
            qs.exclude(tag='')
            .order_by()
            .values('tag')
            .annotate(first_id=Min('pk'))
            .values('first_id')
        )
        qs = qs.filter(Q(tag='') | Q(pk__in=Subquery(group_representatives)))
        return Voucher.annotate_budget_used_orders(qs)

    @cached_property
    def filter_form(self):
        return VoucherFilterForm(data=self.request.GET, event=self.request.event)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['advanced_filters_open'] = advanced_filters_open_from_get(self.filter_form)
        ctx['advanced_filter_count'] = advanced_filter_count(self.filter_form)
        vouchers = list(ctx['vouchers'])
        group_tags = {voucher.tag for voucher in vouchers if voucher.tag}
        if group_tags:
            group_totals = {
                total['tag']: total
                for total in self.request.event.vouchers.filter(waitinglistentries__isnull=True, tag__in=group_tags)
                .order_by()
                .values('tag')
                .annotate(group_redeemed=Sum('redeemed'), group_max_usages=Sum('max_usages'))
            }
            for voucher in vouchers:
                if voucher.tag:
                    total = group_totals.get(voucher.tag)
                    voucher.group_redeemed = total['group_redeemed'] if total else 0
                    voucher.group_max_usages = total['group_max_usages'] if total else 0

        return ctx

    def get(self, request, *args, **kwargs):
        if request.GET.get('tab') == 'tags':
            query = request.GET.copy()
            query.pop('tab')
            return HttpResponseRedirect(f'{request.path}?{query.urlencode()}' if query else request.path)
        if request.GET.get('download', '') == 'yes':
            return self._download_csv()
        return super().get(request, *args, **kwargs)

    def _download_csv(self):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC, delimiter=',')

        headers = [
            _('Voucher code'),
            _('Voucher link'),
            _('Valid until'),
            _('Product'),
            _('Reserve quota'),
            _('Bypass quota'),
            _('Bypass approval'),
            _('Price effect'),
            _('Value'),
            _('Tag'),
            _('Redeemed'),
            _('Maximum usages'),
            _('Seat'),
            _('Comment'),
        ]
        writer.writerow(headers)

        base_url = build_absolute_uri(self.request.event, 'presale:event.redeem')

        for v in Voucher.annotate_budget_used_orders(self.get_filtered_queryset()):
            url = f'{base_url}?voucher={quote_plus(v.code)}'
            if v.subevent_id and v.subevent and v.subevent.event_id == self.request.event.pk and v.subevent.active:
                url += f'&subevent={v.subevent_id}'
            if v.limit_products.exists() or v.limit_variations.exists():
                parts = [str(p) for p in v.limit_products.all()]
                parts += ['%s – %s' % (str(var.product), str(var)) for var in v.limit_variations.all()]
                prod = ', '.join(parts)
            elif v.product:
                if v.variation:
                    prod = '%s – %s' % (str(v.product), str(v.variation))
                else:
                    prod = '%s' % str(v.product)
            elif v.quota:
                prod = _('Any product in quota "{quota}"').format(quota=str(v.quota.name))
            else:
                prod = _('Any product')
            row = [
                v.code,
                url,
                v.valid_until.isoformat() if v.valid_until else '',
                prod,
                _('Yes') if v.block_quota else _('No'),
                _('Yes') if v.allow_ignore_quota else _('No'),
                _('Yes') if v.allow_ignore_approval else _('No'),
                v.get_price_mode_display(),
                str(v.value) if v.value is not None else '',
                v.tag,
                str(v.redeemed),
                str(v.max_usages),
                str(v.seat) if v.seat else '',
                str(v.comment) if v.comment else '',
            ]
            writer.writerow(row)

        r = HttpResponse(output.getvalue().encode('utf-8'), content_type='text/csv')
        r['Content-Disposition'] = 'attachment; filename="vouchers.csv"'
        return r


class VoucherGroupMembers(EventPermissionRequiredMixin, View):
    permission = 'can_view_vouchers'
    MEMBER_PAGE_SIZE = 50

    def get(self, request, *args, **kwargs):
        try:
            group_representative = request.event.vouchers.get(pk=kwargs['voucher'])
        except Voucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

        if not group_representative.tag:
            raise Http404(_('The requested voucher does not belong to a group.'))

        try:
            after = int(request.GET.get('after') or 0)
        except ValueError:
            return HttpResponseBadRequest()
        if after < 0:
            return HttpResponseBadRequest()

        members = Voucher.annotate_budget_used_orders(
            request.event.vouchers.filter(
                waitinglistentries__isnull=True,
                tag=group_representative.tag,
                pk__gt=after,
            )
            .select_related('product', 'variation', 'seat', 'quota', 'subevent')
            .prefetch_related('limit_products', 'limit_variations', 'limit_variations__product')
            .order_by('pk')
        )
        members = list(members[: self.MEMBER_PAGE_SIZE + 1])
        next_members_url = None
        if len(members) > self.MEMBER_PAGE_SIZE:
            next_members_url = '{}?after={}'.format(
                reverse(
                    'control:event.voucher.members',
                    kwargs={
                        'organizer': request.event.organizer.slug,
                        'event': request.event.slug,
                        'voucher': group_representative.pk,
                    },
                ),
                members[self.MEMBER_PAGE_SIZE - 1].pk,
            )
            members = members[: self.MEMBER_PAGE_SIZE]

        return render(
            request,
            'pretixcontrol/vouchers/_voucher_group_members.html',
            {
                'group_id': group_representative.pk,
                'members': members,
                'next_members_url': next_members_url,
            },
        )


class VoucherDelete(EventPermissionRequiredMixin, DeleteView):
    model = Voucher
    template_name = 'pretixcontrol/vouchers/delete.html'
    permission = 'can_change_vouchers'
    context_object_name = 'voucher'

    def get_object(self, queryset=None) -> Voucher:
        try:
            return self.request.event.vouchers.get(id=self.kwargs['voucher'])
        except Voucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get(self, request, *args, **kwargs):
        if not self.get_object().allow_delete():
            messages.error(
                request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()

        if not self.object.allow_delete():
            messages.error(
                self.request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
        else:
            self.object.log_action('eventyay.voucher.deleted', user=self.request.user)
            CartPosition.objects.filter(addon_to__voucher=self.object).delete()
            self.object.cartposition_set.all().delete()
            self.object.delete()
            messages.success(self.request, _('The selected voucher has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


def voucher_group_queryset(event, tags=None, ids=None):
    if not tags and not ids:
        return event.vouchers.none()
    query = Q()
    if tags:
        query |= Q(tag__in=tags)
    if ids:
        query |= Q(pk__in=ids)
    return event.vouchers.filter(query, waitinglistentries__isnull=True).distinct()


def voucher_group_mixed_fields(objects, instance):
    mixed_fields = {
        field
        for field in (
            'tag',
            'valid_until',
            'block_quota',
            'allow_ignore_quota',
            'allow_ignore_approval',
            'value',
            'max_usages',
            'price_mode',
            'subevent',
            'show_hidden_products',
            'all_addons_included',
            'all_bundles_included',
            'budget',
            'comment',
        )
        if objects.exclude(**{field: getattr(instance, field)}).exists()
    }
    product_values = {
        (
            voucher.quota_id,
            voucher.product_id,
            voucher.variation_id,
            tuple(voucher.limit_products.values_list('pk', flat=True)),
            tuple(voucher.limit_variations.values_list('pk', flat=True)),
        )
        for voucher in objects
    }
    if len(product_values) > 1:
        mixed_fields.add('productvar')
    return mixed_fields


class VoucherGroupDelete(EventPermissionRequiredMixin, View):
    permission = 'can_change_vouchers'

    def get_objects(self):
        try:
            representative = self.request.event.vouchers.get(pk=self.kwargs['voucher'])
        except Voucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))
        if not representative.tag:
            raise Http404(_('The requested voucher does not belong to a group.'))
        return voucher_group_queryset(self.request.event, tags=[representative.tag]), representative.tag

    def get(self, request, *args, **kwargs):
        objects, tag = self.get_objects()
        return render(
            request,
            'pretixcontrol/vouchers/delete_group.html',
            {
                'group_name': tag,
                'unused_count': objects.filter(redeemed=0, orderposition__isnull=True).count(),
                'used_count': objects.exclude(redeemed=0, orderposition__isnull=True).count(),
            },
        )

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        objects, tag = self.get_objects()
        object_ids = list(objects.values_list('pk', flat=True))
        objects = list(
            self.request.event.vouchers.filter(pk__in=object_ids)
            .select_for_update()
        )
        for obj in objects:
            if obj.redeemed or obj.orderposition_set.exists():
                continue
            obj.log_action('eventyay.voucher.deleted', user=request.user)
            CartPosition.objects.filter(addon_to__voucher=obj).delete()
            obj.cartposition_set.all().delete()
            obj.delete()
        messages.success(request, _('The unused vouchers in group "%s" have been deleted.') % tag)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(
            'control:event.vouchers',
            kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug},
        )


class VoucherGroupUpdate(EventPermissionRequiredMixin, FormView):
    permission = 'can_change_vouchers'
    template_name = 'pretixcontrol/vouchers/group_form.html'

    def get_form_class(self):
        form_class = VoucherGroupForm
        for receiver, response in voucher_form_class.send(self.request.event, cls=form_class):
            if response:
                form_class = response
        return form_class

    def get_objects(self):
        if self.request.POST.getlist('voucher') or self.request.POST.getlist('voucher_group'):
            selected_groups = self.request.POST.getlist('voucher_group')
            tags = self.request.event.vouchers.filter(pk__in=selected_groups).exclude(tag='').values_list('tag', flat=True)
            return voucher_group_queryset(
                self.request.event,
                tags=tags,
                ids=self.request.POST.getlist('voucher'),
            ).exclude(pk__in=self.request.POST.getlist('voucher_exclude'))
        try:
            representative = self.request.event.vouchers.get(pk=self.kwargs['voucher'])
        except Voucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))
        if not representative.tag:
            raise Http404(_('The requested voucher does not belong to a group.'))
        return voucher_group_queryset(self.request.event, tags=[representative.tag])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        objects = self.get_objects()
        instance = objects.order_by('pk').first()
        if instance is None:
            raise Http404(_('The requested vouchers do not exist.'))
        kwargs['instance'] = instance
        mixed_fields = voucher_group_mixed_fields(objects, instance)
        kwargs['mixed_fields'] = mixed_fields
        kwargs.setdefault('initial', {}).update({field: None for field in mixed_fields})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selection_voucher_ids'] = self.request.POST.getlist('voucher')
        context['selection_group_ids'] = self.request.POST.getlist('voucher_group')
        context['selection_excluded_voucher_ids'] = self.request.POST.getlist('voucher_exclude')
        context['voucher_codes'] = self.get_objects().order_by('pk').values_list('code', flat=True)
        context['mixed_fields'] = getattr(context['form'], 'mixed_fields', set())
        return context

    def get_changed_fields(self, objects, form):
        changed_fields = set(form.changed_data) - {'seat'}
        for field in form.mixed_fields:
            if not form.cleaned_data.get(field):
                changed_fields.discard(field)
        scalar_fields = set(form.cleaned_data) - {'productvar', 'seat'} - form.mixed_fields
        scalar_fields.update(field for field in form.mixed_fields if form.cleaned_data.get(field))
        for field in scalar_fields:
            if any(getattr(obj, field, None) != form.cleaned_data[field] for obj in objects):
                changed_fields.add(field)
        if 'productvar' not in form.mixed_fields or form.cleaned_data.get('productvar'):
            product_changed = any(
            obj.quota_id != form.instance.quota_id
            or obj.product_id != form.instance.product_id
            or obj.variation_id != form.instance.variation_id
            or {p.pk for p in obj.limit_products.all()} != {p.pk for p in form._limit_products}
            or {v.pk for v in obj.limit_variations.all()} != {v.pk for v in form._limit_variations}
            for obj in objects
            )
            if product_changed:
                changed_fields.add('productvar')
        return changed_fields

    def skipped_objects(self, objects, form, changed_fields):
        skip_query = Q(redeemed__gte=F('max_usages'))
        if 'max_usages' in changed_fields:
            skip_query |= Q(redeemed__gt=form.cleaned_data['max_usages'])
        if hasattr(objects, 'filter'):
            return objects.filter(skip_query)
        return [obj for obj in objects if obj.redeemed >= obj.max_usages or (
            'max_usages' in changed_fields and obj.redeemed > form.cleaned_data['max_usages']
        )]

    def skipped_object_ids(self, objects, form, changed_fields):
        skipped = self.skipped_objects(objects, form, changed_fields)
        skipped_ids = {obj.pk for obj in skipped}
        reasons = {
            'fully_used': 0,
            'max_too_low': 0,
            'seat_incompatible': 0,
        }
        for obj in objects:
            if obj.pk in skipped_ids:
                if obj.redeemed >= obj.max_usages:
                    reasons['fully_used'] += 1
                elif 'max_usages' in changed_fields:
                    reasons['max_too_low'] += 1
        if 'productvar' in changed_fields:
            for obj in objects:
                if (
                    obj.pk not in skipped_ids
                    and obj.seat_id
                    and (not form.instance.product_id or obj.seat.product_id != form.instance.product_id)
                ):
                    skipped_ids.add(obj.pk)
                    reasons['seat_incompatible'] += 1
        return skipped_ids, reasons

    def validate_quota_delta(self, objects, form, changed_fields):
        now = timezone.now()
        quota_delta = {}

        def add_targets(targets, amount):
            for target in targets:
                quota_delta[target] = quota_delta.get(target, 0) + amount

        def targets_for(voucher, *, new=False):
            if new:
                block_quota = form.cleaned_data['block_quota'] if 'block_quota' in changed_fields else voucher.block_quota
                allow_ignore_quota = (
                    form.cleaned_data['allow_ignore_quota']
                    if 'allow_ignore_quota' in changed_fields
                    else voucher.allow_ignore_quota
                )
                valid_until = (
                    form.cleaned_data['valid_until'] if 'valid_until' in changed_fields else voucher.valid_until
                )
                subevent = form.cleaned_data['subevent'] if 'subevent' in changed_fields else voucher.subevent
                quota = form.instance.quota if 'productvar' in changed_fields else voucher.quota
                product = form.instance.product if 'productvar' in changed_fields else voucher.product
                variation = form.instance.variation if 'productvar' in changed_fields else voucher.variation
                limit_products = (
                    getattr(form, '_limit_products', [])
                    if 'productvar' in changed_fields
                    else voucher.limit_products.all()
                )
                limit_variations = (
                    getattr(form, '_limit_variations', [])
                    if 'productvar' in changed_fields
                    else voucher.limit_variations.all()
                )
                if not block_quota or allow_ignore_quota or (valid_until is not None and valid_until < now):
                    return set()
            else:
                if not voucher.block_quota or voucher.allow_ignore_quota or (
                    voucher.valid_until is not None and voucher.valid_until < now
                ):
                    return set()
                subevent = voucher.subevent
                quota = voucher.quota
                product = voucher.product
                variation = voucher.variation
                limit_products = voucher.limit_products.all()
                limit_variations = voucher.limit_variations.all()
            if quota:
                return {quota}
            targets = set(limit_variations)
            targets.update(p for p in limit_products if not p.has_variations)
            if variation:
                targets.add(variation)
            elif product and not product.has_variations:
                targets.add(product)
            return {
                quota
                for target in targets
                for quota in target.quotas.filter(subevent=subevent)
            }

        for obj in objects:
            max_usages = form.cleaned_data['max_usages'] if 'max_usages' in changed_fields else obj.max_usages
            remaining_old = max(0, obj.max_usages - obj.redeemed)
            remaining_new = max(0, max_usages - obj.redeemed)
            add_targets(targets_for(obj), -remaining_old)
            add_targets(targets_for(obj, new=True), remaining_new)
        for quota, delta in quota_delta.items():
            if delta <= 0:
                continue
            availability = quota.availability(count_waitinglist=False)
            if availability[0] != Quota.AVAILABILITY_OK or (
                availability[1] is not None and availability[1] < delta
            ):
                raise ValidationError(
                    _(
                        'You cannot create a voucher that blocks quota as the selected product or '
                        'quota is currently sold out or completely reserved.'
                    )
                )

    def preview_context(self, form):
        objects = list(self.get_objects().select_related('seat').prefetch_related('limit_products', 'limit_variations'))
        changed_fields = self.get_changed_fields(objects, form)
        skipped_ids, reasons = self.skipped_object_ids(objects, form, changed_fields)
        return {
            'form': form,
            'selection_voucher_ids': self.request.POST.getlist('voucher'),
            'selection_group_ids': self.request.POST.getlist('voucher_group'),
            'selection_excluded_voucher_ids': self.request.POST.getlist('voucher_exclude'),
            'voucher_codes': [obj.code for obj in objects],
            'update_count': len(objects) - len(skipped_ids),
            'skip_count': len(skipped_ids),
            'fully_used_count': reasons['fully_used'],
            'max_too_low_count': reasons['max_too_low'],
            'seat_incompatible_count': reasons['seat_incompatible'],
            'preview': True,
        }

    @transaction.atomic
    def form_valid(self, form):
        object_ids = list(self.get_objects().values_list('pk', flat=True))
        objects = list(
            self.request.event.vouchers.filter(pk__in=object_ids)
            .prefetch_related('limit_products', 'limit_variations')
            .select_for_update()
        )
        if self.request.POST.get('confirm') != '1':
            return self.render_to_response(self.preview_context(form))
        changed_fields = self.get_changed_fields(objects, form)
        skipped_ids, _skipped_reasons = self.skipped_object_ids(objects, form, changed_fields)
        if not changed_fields:
            messages.info(self.request, _('No voucher changes were submitted.'))
            return redirect(self.get_success_url())
        eligible_objects = [obj for obj in objects if obj.pk not in skipped_ids]
        try:
            self.validate_quota_delta(eligible_objects, form, changed_fields)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        changed_data = {
            field: form.cleaned_data[field]
            for field in changed_fields
            if field not in {'productvar', 'seat'}
        }
        if 'productvar' in changed_fields:
            changed_data.update(
                product=form.instance.product,
                variation=form.instance.variation,
                quota=form.instance.quota,
            )
        updated_count = 0
        log_data = {}
        for field, value in changed_data.items():
            if field in {'product', 'variation', 'quota', 'subevent'}:
                log_data[f'{field}_id'] = value.pk if value else None
            else:
                log_data[field] = value
        for obj in objects:
            if obj.pk in skipped_ids:
                continue
            for field, value in changed_data.items():
                setattr(obj, field, value)
            obj.save()
            if 'productvar' in changed_fields:
                obj.limit_products.set(form._limit_products)
                obj.limit_variations.set(form._limit_variations)
            if changed_data:
                obj.log_action('eventyay.voucher.changed', user=self.request.user, data=log_data)
            updated_count += 1
        messages.success(
            self.request,
            _('Updated %(updated)s vouchers. Skipped %(skipped)s vouchers.') % {
                'updated': updated_count,
                'skipped': len(skipped_ids),
            },
        )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(
            'control:event.vouchers',
            kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug},
        )


class VoucherUpdate(EventPermissionRequiredMixin, UpdateView):
    model = Voucher
    template_name = 'pretixcontrol/vouchers/detail.html'
    permission = 'can_change_vouchers'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = VoucherForm
        for receiver, response in voucher_form_class.send(self.request.event, cls=form_class):
            if response:
                form_class = response
        return form_class

    def get_object(self, queryset=None) -> VoucherForm:
        url = resolve(self.request.path_info)
        try:
            return self.request.event.vouchers.get(id=url.kwargs['voucher'])
        except Voucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        if form.has_changed():
            self.object.log_action(
                'eventyay.voucher.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class VoucherCreate(EventPermissionRequiredMixin, CreateView):
    model = Voucher
    template_name = 'pretixcontrol/vouchers/detail.html'
    permission = 'can_change_vouchers'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = VoucherForm
        for receiver, response in voucher_form_class.send(self.request.event, cls=form_class):
            if response:
                form_class = response
        return form_class

    def get_success_url(self) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Voucher(event=self.request.event)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        url = reverse(
            'control:event.voucher',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'voucher': self.object.pk,
            },
        )
        messages.success(
            self.request,
            mark_safe(
                _('The new voucher has been created: {code}').format(
                    code=format_html('<a href="{url}">{code}</a>', url=url, code=self.object.code)
                )
            ),
        )
        form.instance.log_action('eventyay.voucher.added', data=dict(form.cleaned_data), user=self.request.user)
        return ret

    def post(self, request, *args, **kwargs):
        # TODO: Transform this into an asynchronous call?
        with request.event.lock():
            return super().post(request, *args, **kwargs)


class VoucherGo(EventPermissionRequiredMixin, View):
    permission = 'can_view_vouchers'

    def get_voucher(self, code):
        return Voucher.objects.get(code__iexact=code, event=self.request.event)

    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', '').strip()
        try:
            voucher = self.get_voucher(code)
            return redirect(
                'control:event.voucher',
                event=request.event.slug,
                organizer=request.event.organizer.slug,
                voucher=voucher.id,
            )
        except Voucher.DoesNotExist:
            messages.error(request, _('There is no voucher with the given voucher code.'))
            return redirect(
                'control:event.vouchers',
                event=request.event.slug,
                organizer=request.event.organizer.slug,
            )


class VoucherBulkCreate(EventPermissionRequiredMixin, AsyncFormView):
    model = Voucher
    template_name = 'pretixcontrol/vouchers/bulk.html'
    permission = 'can_change_vouchers'
    context_object_name = 'voucher'

    def get_success_url(self, value) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def get_error_url(self):
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    @cached_property
    def copy_from(self):
        if self.request.GET.get('copy_from') and not getattr(self, 'object', None):
            try:
                return self.request.event.vouchers.get(pk=self.request.GET.get('copy_from'))
            except Voucher.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if self.copy_from:
            i = modelcopy(self.copy_from)
            i.pk = None
            i.redeemed = 0
            kwargs['instance'] = i
            if self.copy_from.limit_products.exists() or self.copy_from.limit_variations.exists():
                kwargs.setdefault('initial', {})
                kwargs['initial']['productvar'] = [str(p.pk) for p in self.copy_from.limit_products.all()] + [
                    '%d-%d' % (v.product_id, v.pk) for v in self.copy_from.limit_variations.all()
                ]
        else:
            kwargs['instance'] = Voucher(event=self.request.event, code=None)
        return kwargs

    def get_async_form_kwargs(self, form_kwargs, organizer=None, event=None):
        if not form_kwargs.get('instance'):
            form_kwargs['instance'] = Voucher(event=self.request.event, code=None)
        return form_kwargs

    def async_form_valid(self, task, form):
        lockfn = NoLockManager
        if form.data.get('block_quota'):
            lockfn = self.request.event.lock
        batch_size = 500
        total_num = 1  # will be set later

        def set_progress(percent):
            if not task.request.called_directly:
                task.update_state(state='PROGRESS', meta={'value': percent})

        def process_batch(batch_vouchers, voucherids):
            Voucher.objects.bulk_create(batch_vouchers)
            if not connection.features.can_return_rows_from_bulk_insert:
                batch_vouchers = list(self.request.event.vouchers.filter(code__in=[v.code for v in batch_vouchers]))

            log_entries = []
            for v in batch_vouchers:
                voucherids.append(v.pk)
                data = dict(form.cleaned_data)
                data['code'] = code
                data['bulk'] = True
                del data['codes']
                log_entries.append(
                    v.log_action(
                        'eventyay.voucher.added',
                        data=data,
                        user=self.request.user,
                        save=False,
                    )
                )
            LogEntry.objects.bulk_create(log_entries)
            form.post_bulk_save(batch_vouchers)
            batch_vouchers.clear()
            set_progress(len(voucherids) / total_num * (50.0 if form.cleaned_data['send'] else 100.0))

        voucherids = []
        with lockfn(), transaction.atomic():
            if not form.is_valid():
                raise ValidationError(form.errors)
            total_num = len(form.cleaned_data['codes'])

            batch_vouchers = []
            for code in form.cleaned_data['codes']:
                if len(batch_vouchers) > batch_size:
                    process_batch(batch_vouchers, voucherids)

                obj = modelcopy(form.instance, code=None)
                obj.event = self.request.event
                obj.code = code
                try:
                    obj.seat = form.cleaned_data['seats'].pop()
                    obj.product = obj.seat.product
                except IndexError:
                    pass
                batch_vouchers.append(obj)

            process_batch(batch_vouchers, voucherids)

        if form.cleaned_data['send']:
            vouchers_send(
                event=self.request.event,
                vouchers=voucherids,
                subject=form.cleaned_data['send_subject'],
                message=form.cleaned_data['send_message'],
                recipients=[r._asdict() for r in form.cleaned_data['send_recipients']],
                user=self.request.user.pk,
                progress=lambda p: set_progress(50.0 + p * 50.0),
            )

    def get_success_message(self, value):
        return _('The new vouchers have been created.')

    def get_form_class(self):
        form_class = VoucherBulkForm
        for receiver, response in voucher_form_class.send(self.request.event, cls=form_class):
            if response:
                form_class = response
        return form_class

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['code_length'] = settings.ENTROPY['voucher_code']
        ctx['max_codes'] = VoucherRNG.MAX_CODES
        ctx['max_prefix_length'] = VoucherRNG.get_max_prefix_length()
        return ctx


class VoucherRNG(EventPermissionRequiredMixin, View):
    permission = 'can_change_vouchers'
    MAX_CODES = 1_000

    @staticmethod
    def get_max_prefix_length() -> int:
        return Voucher._meta.get_field('code').max_length - settings.ENTROPY['voucher_code']

    def get(self, request, *args, **kwargs):
        codes = set()
        try:
            num = int(request.GET.get('num', '5'))
        except ValueError:  # NOQA
            return HttpResponseBadRequest()

        if num < 0 or num > self.MAX_CODES:
            # The codes are generated inside the request, so time and memory
            # grow with ``num``.
            return HttpResponseBadRequest()

        prefix = request.GET.get('prefix', '')
        if len(prefix) > self.get_max_prefix_length():
            return HttpResponseBadRequest()
        while len(codes) < num:
            new_codes = set()
            for i in range(min(num - len(codes), 500)):  # Work around SQLite's SQLITE_MAX_VARIABLE_NUMBER
                new_codes.add(_generate_random_code(prefix=prefix))
            new_codes -= set([v['code'] for v in Voucher.objects.filter(code__in=new_codes).values('code')])
            codes |= new_codes

        return JsonResponse({'codes': list(codes)})

    def get_success_url(self) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class VoucherBulkAction(EventPermissionRequiredMixin, View):
    permission = 'can_change_vouchers'

    @cached_property
    def objects(self):
        selected_vouchers = Q(id__in=self.request.POST.getlist('voucher'))
        selected_groups = self.request.POST.getlist('voucher_group')
        if selected_groups:
            selected_group_tags = (
                self.request.event.vouchers.filter(id__in=selected_groups).exclude(tag='').order_by().values('tag')
            )
            selected_vouchers |= Q(tag__in=Subquery(selected_group_tags), waitinglistentries__isnull=True)

        return self.request.event.vouchers.filter(selected_vouchers).exclude(
            id__in=self.request.POST.getlist('voucher_exclude')
        ).distinct()

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if not self.objects.exists():
            return redirect(self.get_success_url())

        if request.POST.get('action') == 'delete':
            return render(
                request,
                'pretixcontrol/vouchers/delete_bulk.html',
                {
                    'allowed_count': self.objects.filter(redeemed=0, orderposition__isnull=True).count(),
                    'forbidden_count': self.objects.exclude(redeemed=0, orderposition__isnull=True).count(),
                    'voucher_ids': self.objects.values_list('pk', flat=True),
                },
            )
        elif request.POST.get('action') == 'edit':
            first = self.objects.order_by('pk').first()
            form_class = VoucherGroupForm
            for receiver, response in voucher_form_class.send(request.event, cls=form_class):
                if response:
                    form_class = response
            form = form_class(
                instance=first,
                mixed_fields=voucher_group_mixed_fields(self.objects, first),
                initial={field: None for field in voucher_group_mixed_fields(self.objects, first)},
            )
            return render(
                request,
                'pretixcontrol/vouchers/group_form.html',
                {
                    'form': form,
                    'selection_voucher_ids': request.POST.getlist('voucher'),
                    'selection_group_ids': request.POST.getlist('voucher_group'),
                    'selection_excluded_voucher_ids': request.POST.getlist('voucher_exclude'),
                    'mixed_fields': form.mixed_fields,
                    'voucher_codes': self.objects.order_by('pk').values_list('code', flat=True),
                    'action_url': reverse(
                        'control:event.voucher.group_edit',
                        kwargs={
                            'organizer': request.event.organizer.slug,
                            'event': request.event.slug,
                            'voucher': first.pk,
                        },
                    ),
                },
            )
        elif request.POST.get('action') == 'delete_confirm':
            object_ids = list(self.objects.values_list('pk', flat=True))
            locked_objects = list(self.request.event.vouchers.filter(pk__in=object_ids).select_for_update())
            deleted_count = 0
            kept_count = 0
            for obj in locked_objects:
                if obj.redeemed or obj.orderposition_set.exists():
                    kept_count += 1
                    continue
                obj.log_action('eventyay.voucher.deleted', user=self.request.user)
                CartPosition.objects.filter(addon_to__voucher=obj).delete()
                obj.cartposition_set.all().delete()
                obj.delete()
                deleted_count += 1

            if kept_count:
                messages.warning(
                    request,
                    ngettext(
                        '%(count)d used voucher was kept. Existing orders were not affected.',
                        '%(count)d used vouchers were kept. Existing orders were not affected.',
                        kept_count,
                    )
                    % {'count': kept_count},
                )
            if deleted_count:
                messages.success(
                    request,
                    ngettext(
                        '%(count)d unused voucher was deleted.',
                        '%(count)d unused vouchers were deleted.',
                        deleted_count,
                    )
                    % {'count': deleted_count},
                )
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse(
            'control:event.vouchers',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )
