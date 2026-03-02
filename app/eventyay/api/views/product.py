import django_filters
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from eventyay.api.serializers.product import (
    ProductAddOnSerializer,
    ProductBundleSerializer,
    ProductCategorySerializer,
    ProductSerializer,
    ProductVariationSerializer,
    QuestionOptionSerializer,
    QuestionSerializer,
    QuotaSerializer,
)
from eventyay.api.views import ConditionalListView
from eventyay.base.models import (
    CartPosition,
    Product,
    ProductAddOn,
    ProductBundle,
    ProductCategory,
    ProductVariation,
    Question,
    QuestionOption,
    Quota,
)
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.helpers.dicts import merge_dicts

with scopes_disabled():

    class ProductFilter(FilterSet):
        tax_rate = django_filters.CharFilter(method='tax_rate_qs')

        def tax_rate_qs(self, queryset, name, value):
            if value in ('0', 'None', '0.00'):
                return queryset.filter(Q(tax_rule__isnull=True) | Q(tax_rule__rate=0))
            else:
                return queryset.filter(tax_rule__rate=value)

        class Meta:
            model = Product
            fields = ['active', 'category', 'admission', 'tax_rate', 'free_price']


class ProductViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.none()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    ordering_fields = ('id', 'position')
    ordering = ('position', 'id')
    filterset_class = ProductFilter
    permission = None
    write_permission = 'can_change_items'

    def get_queryset(self):
        return (
            self.request.event.products.select_related('tax_rule')
            .prefetch_related('variations', 'addons', 'bundles', 'meta_values')
            .all()
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.product.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        return ctx

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data

        serializer.save(event=self.request.event)

        if serializer.data == original_data:
            # Performance optimization: If nothing was changed, we do not need to save or log anything.
            # This costs us a few cycles on save, but avoids thousands of lines in our log.
            return
        serializer.instance.log_action(
            'eventyay.event.product.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                'This product cannot be deleted because it has already been ordered '
                "by a user or currently is in a users's cart. Please set the product as "
                '"inactive" instead.'
            )

        instance.log_action(
            'eventyay.event.product.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        CartPosition.objects.filter(addon_to__product=instance).delete()
        instance.cartposition_set.all().delete()
        super().perform_destroy(instance)


class ProductVariationViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariationSerializer
    queryset = ProductVariation.objects.none()
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    ordering_fields = ('id', 'position')
    ordering = ('id',)
    permission = None
    write_permission = 'can_change_items'

    @cached_property
    def product(self):
        return get_object_or_404(Product, pk=self.kwargs['product'], event=self.request.event)

    def get_queryset(self):
        return self.product.variations.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['product'] = self.product
        return ctx

    def perform_create(self, serializer):
        product = self.product
        if not product.has_variations:
            raise PermissionDenied(
                'This variation cannot be created because the product does not have variations. '
                'Changing a product without variations to a product with variations is not allowed.'
            )
        serializer.save(product=product)
        product.log_action(
            'eventyay.event.product.variation.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
                {'value': serializer.instance.value},
            ),
        )

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.product.log_action(
            'eventyay.event.product.variation.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
                {'value': serializer.instance.value},
            ),
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                'This variation cannot be deleted because it has already been ordered '
                "by a user or currently is in a users's cart. Please set the variation as "
                "'inactive' instead."
            )
        if instance.is_only_variation():
            raise PermissionDenied(
                'This variation cannot be deleted because it is the only variation. Changing a '
                'product with variations to a product without variations is not allowed.'
            )
        super().perform_destroy(instance)
        instance.product.log_action(
            'eventyay.event.product.variation.deleted',
            user=self.request.user,
            auth=self.request.auth,
            data={'value': instance.value, 'id': self.kwargs['pk']},
        )


class ProductBundleViewSet(viewsets.ModelViewSet):
    serializer_class = ProductBundleSerializer
    queryset = ProductBundle.objects.none()
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    ordering_fields = ('id',)
    ordering = ('id',)
    permission = None
    write_permission = 'can_change_items'

    @cached_property
    def product(self):
        return get_object_or_404(Product, pk=self.kwargs['product'], event=self.request.event)

    def get_queryset(self):
        return self.product.bundles.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        ctx['product'] = self.product
        return ctx

    def perform_create(self, serializer):
        product = get_object_or_404(Product, pk=self.kwargs['product'], event=self.request.event)
        serializer.save(base_product=product)
        product.log_action(
            'eventyay.event.product.bundles.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': serializer.instance.pk}),
        )

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.base_product.log_action(
            'eventyay.event.product.bundles.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': serializer.instance.pk}),
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        instance.base_product.log_action(
            'eventyay.event.product.bundles.removed',
            user=self.request.user,
            auth=self.request.auth,
            data={
                'bundled_product': instance.bundled_product.pk,
                'bundled_variation': instance.bundled_variation.pk if instance.bundled_variation else None,
                'count': instance.count,
                'designated_price': instance.designated_price,
            },
        )


class ProductAddOnViewSet(viewsets.ModelViewSet):
    serializer_class = ProductAddOnSerializer
    queryset = ProductAddOn.objects.none()
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    ordering_fields = ('id', 'position')
    ordering = ('id',)
    permission = None
    write_permission = 'can_change_items'

    @cached_property
    def product(self):
        return get_object_or_404(Product, pk=self.kwargs['product'], event=self.request.event)

    def get_queryset(self):
        return self.product.addons.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        ctx['product'] = self.product
        return ctx

    def perform_create(self, serializer):
        product = self.product
        category = get_object_or_404(ProductCategory, pk=self.request.data['addon_category'])
        serializer.save(base_product=product, addon_category=category)
        product.log_action(
            'eventyay.event.product.addons.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
            ),
        )

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.base_product.log_action(
            'eventyay.event.product.addons.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
            ),
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        instance.base_product.log_action(
            'eventyay.event.product.addons.removed',
            user=self.request.user,
            auth=self.request.auth,
            data={'category': instance.addon_category.pk},
        )


class ProductCategoryFilter(FilterSet):
    class Meta:
        model = ProductCategory
        fields = ['is_addon']


class ProductCategoryViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = ProductCategorySerializer
    queryset = ProductCategory.objects.none()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = ProductCategoryFilter
    ordering_fields = ('id', 'position')
    ordering = ('position', 'id')
    permission = None
    write_permission = 'can_change_items'

    def get_queryset(self):
        return self.request.event.categories.all()

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.category.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        return ctx

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.category.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        for product in instance.products.all():
            product.category = None
            product.save()
        instance.log_action(
            'eventyay.event.category.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        super().perform_destroy(instance)


with scopes_disabled():

    class QuestionFilter(FilterSet):
        class Meta:
            model = Question
            fields = ['ask_during_checkin', 'required', 'identifier']


class QuestionViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = QuestionSerializer
    queryset = Question.objects.none()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = QuestionFilter
    ordering_fields = ('id', 'position')
    ordering = ('position', 'id')
    permission = None
    write_permission = 'can_change_items'

    def get_queryset(self):
        return self.request.event.questions.prefetch_related('options').all()

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.question.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        return ctx

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.question.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        instance.log_action(
            'eventyay.event.question.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        super().perform_destroy(instance)


class QuestionOptionViewSet(viewsets.ModelViewSet):
    serializer_class = QuestionOptionSerializer
    queryset = QuestionOption.objects.none()
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    ordering_fields = ('id', 'position')
    ordering = ('position',)
    permission = None
    write_permission = 'can_change_items'

    def get_queryset(self):
        q = get_object_or_404(Question, pk=self.kwargs['question'], event=self.request.event)
        return q.options.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        ctx['question'] = get_object_or_404(Question, pk=self.kwargs['question'], event=self.request.event)
        return ctx

    def perform_create(self, serializer):
        q = get_object_or_404(Question, pk=self.kwargs['question'], event=self.request.event)
        serializer.save(question=q)
        q.log_action(
            'eventyay.event.question.option.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
            ),
        )

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.question.log_action(
            'eventyay.event.question.option.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(
                self.request.data,
                {'ORDER': serializer.instance.position},
                {'id': serializer.instance.pk},
            ),
        )

    def perform_destroy(self, instance):
        instance.question.log_action(
            'eventyay.event.question.option.deleted',
            user=self.request.user,
            auth=self.request.auth,
            data={'id': instance.pk},
        )
        super().perform_destroy(instance)


with scopes_disabled():

    class QuotaFilter(FilterSet):
        class Meta:
            model = Quota
            fields = ['subevent']


class QuotaViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = QuotaSerializer
    queryset = Quota.objects.none()
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = QuotaFilter
    ordering_fields = ('id', 'size')
    ordering = ('id',)
    permission = None
    write_permission = 'can_change_items'

    def get_queryset(self):
        return self.request.event.quotas.all()

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        serializer.instance.log_action(
            'eventyay.event.quota.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )
        if serializer.instance.subevent:
            serializer.instance.subevent.log_action(
                'eventyay.subevent.quota.added',
                user=self.request.user,
                auth=self.request.auth,
                data=self.request.data,
            )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['event'] = self.request.event
        return ctx

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data

        current_subevent = serializer.instance.subevent
        serializer.save(event=self.request.event)
        request_subevent = serializer.instance.subevent

        if serializer.data == original_data:
            # Performance optimization: If nothing was changed, we do not need to save or log anything.
            # This costs us a few cycles on save, but avoids thousands of lines in our log.
            return

        if original_data['closed'] is True and serializer.instance.closed is False:
            serializer.instance.log_action(
                'eventyay.event.quota.opened',
                user=self.request.user,
                auth=self.request.auth,
            )
        elif original_data['closed'] is False and serializer.instance.closed is True:
            serializer.instance.log_action(
                'eventyay.event.quota.closed',
                user=self.request.user,
                auth=self.request.auth,
            )

        serializer.instance.log_action(
            'eventyay.event.quota.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )
        if current_subevent == request_subevent:
            if current_subevent is not None:
                current_subevent.log_action(
                    'eventyay.subevent.quota.changed',
                    user=self.request.user,
                    auth=self.request.auth,
                    data=self.request.data,
                )
        else:
            if request_subevent is not None:
                request_subevent.log_action(
                    'eventyay.subevent.quota.added',
                    user=self.request.user,
                    auth=self.request.auth,
                    data=self.request.data,
                )
            if current_subevent is not None:
                current_subevent.log_action(
                    'eventyay.subevent.quota.deleted',
                    user=self.request.user,
                    auth=self.request.auth,
                )
        serializer.instance.rebuild_cache()

    def perform_destroy(self, instance):
        instance.log_action(
            'eventyay.event.quota.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        if instance.subevent:
            instance.subevent.log_action(
                'eventyay.subevent.quota.deleted',
                user=self.request.user,
                auth=self.request.auth,
            )
        super().perform_destroy(instance)

    @action(detail=True, methods=['get'])
    def availability(self, request, *args, **kwargs):
        quota = self.get_object()

        qa = QuotaAvailability()
        qa.queue(quota)
        qa.compute()
        avail = qa.results[quota]

        data = {
            'paid_orders': qa.count_paid_orders[quota],
            'pending_orders': qa.count_pending_orders[quota],
            'exited_orders': qa.count_exited_orders[quota],
            'blocking_vouchers': qa.count_vouchers[quota],
            'cart_positions': qa.count_cart[quota],
            'waiting_list': qa.count_pending_orders[quota],
            'available_number': avail[1],
            'available': avail[0] == Quota.AVAILABILITY_OK,
            'total_size': quota.size,
        }
        return Response(data)
