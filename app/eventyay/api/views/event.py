import json
import logging
from contextlib import suppress

import django_filters
import jwt
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_scopes import scopes_disabled
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, filters, status, views, viewsets
from rest_framework.authentication import get_authorization_header
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.api.auth.api_auth import (
    ApiAccessRequiredPermission,
    EventPermissions,
    UserDeletePermissions,
)
from eventyay.api.auth.permission import CloneEventPermission, EventCRUDPermission, EventPermission
from eventyay.api.serializers.event import (
    CloneEventSerializer,
    EventSettingsSerializer,
    SubEventSerializer,
    TaxRuleSerializer,
)
from eventyay.api.serializers.event import (
    EventSerializer as ApiEventSerializer,
)
from eventyay.api.serializers.rooms import EventSerializer as RoomsEventSerializer
from eventyay.api.utils import get_protocol
from eventyay.api.views import ConditionalListView
from eventyay.base.models import Device, Organizer, SubEvent, TaxRule, TeamAPIToken, User
from eventyay.base.models.event import Event
from eventyay.base.payment import ManualPayment
from eventyay.base.services.event import notify_event_change
from eventyay.base.settings import SETTINGS_AFFECTING_CSS
from eventyay.eventyay_common.video.permissions import VIDEO_TRAIT_ROLE_MAP
from eventyay.helpers.dicts import merge_dicts
from eventyay.presale.style import regenerate_css
from eventyay.presale.views.organizer import filter_qs_by_attr


logger = logging.getLogger(__name__)

with scopes_disabled():

    class EventFilter(FilterSet):
        is_past = django_filters.rest_framework.BooleanFilter(method='is_past_qs')
        is_future = django_filters.rest_framework.BooleanFilter(method='is_future_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')
        sales_channel = django_filters.rest_framework.CharFilter(method='sales_channel_qs')

        class Meta:
            model = Event
            fields = ['is_public', 'live', 'has_subevents']

        def ends_after_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=value))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=value))
            )
            return queryset.filter(expr)

        def is_past_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)

        def is_future_qs(self, queryset, name, value):
            expr = Q(has_subevents=False) & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
            if value:
                return queryset.filter(expr)
            else:
                return queryset.exclude(expr)

        def sales_channel_qs(self, queryset, name, value):
            return queryset.filter(sales_channels__contains=value)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = ApiEventSerializer
    queryset = Event.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    lookup_value_regex = '[^/]+'
    permission_classes = (EventCRUDPermission,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering = ('slug',)
    ordering_fields = ('date_from', 'slug')
    filterset_class = EventFilter

    def get_queryset(self):
        if isinstance(self.request.auth, (TeamAPIToken, Device)):
            qs = self.request.auth.get_events_with_any_permission()
        elif self.request.user.is_authenticated:
            qs = self.request.user.get_events_with_any_permission(self.request)
        else:
            qs = Event.objects.none()

        organizer = getattr(self.request, 'organizer', None)
        if organizer:
            qs = qs.filter(organizer=organizer)

        qs = filter_qs_by_attr(qs, self.request)

        return qs.prefetch_related('meta_values', 'meta_values__property', 'seat_category_mappings')

    def perform_create(self, serializer):
        inst = serializer.save(organizer=self.request.organizer)
        inst.log_action(
            'eventyay.event.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk}),
        )

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data
        serializer.save()
        if serializer.data == original_data:
            return
        serializer.instance.log_action(
            'eventyay.event.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                "The event can not be deleted as it already contains orders. Please set 'live' to false to hide "
                'the event and take the shop offline instead.'
            )
        try:
            with transaction.atomic():
                instance.organizer.log_action(
                    'eventyay.event.deleted',
                    user=self.request.user,
                    auth=self.request.auth,
                    data={
                        'event_id': instance.pk,
                        'name': str(instance.name),
                        'slug': instance.slug,
                        'logentries': list(instance.logentry_set.values_list('pk', flat=True)),
                    },
                )
                instance.delete_sub_objects()
                instance.delete()
        except ProtectedError:
            raise PermissionDenied(
                'The event could not be deleted as some constraints (e.g. data created by plug-ins) do not allow it.'
            )


def serialize_event_for_response(request):
    return ApiEventSerializer(request.event, context={'request': request}).data


class EventPublishTalksView(APIView):
    permission_classes = (EventPermission,)
    permission = 'can_change_event_settings'

    @extend_schema(summary='Publish Talks')
    def post(self, request, organizer, event):
        if not request.event.live:
            return Response(
                {'detail': 'Publish the event before publishing talks.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user if request.user.is_authenticated else None
        with transaction.atomic():
            previous_private = request.event.private_testmode
            request.event.talks_published = True
            request.event.settings.private_testmode_talks = False
            request.event.private_testmode = request.event.settings.get(
                'private_testmode_tickets',
                True,
                as_type=bool,
            )
            request.event.save()
            if previous_private != request.event.private_testmode:
                request.event.log_action(
                    'eventyay.event.private_testmode.deactivated',
                    user=actor,
                    auth=request.auth,
                    data={},
                )

        return Response(serialize_event_for_response(request), status=status.HTTP_200_OK)


class EventPublishTicketsView(APIView):
    permission_classes = (EventPermission,)
    permission = 'can_change_event_settings'

    @extend_schema(summary='Publish Tickets')
    def post(self, request, organizer, event):
        ticketing_ready = request.event.products.exists() and request.event.quotas.exists()
        billing_issue_texts = {str(issue) for issue in request.event.billing_issues()}
        ticket_issues = [str(issue) for issue in request.event.live_issues if str(issue) not in billing_issue_texts]
        if not request.event.live:
            return Response(
                {'detail': 'Publish the event before publishing tickets.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not ticketing_ready:
            return Response(
                {'detail': 'Please set up ticketing before publishing tickets.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ticket_issues:
            return Response(
                {
                    'detail': 'Please resolve the ticketing issues before publishing tickets.',
                    'issues': ticket_issues,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user if request.user.is_authenticated else None
        with transaction.atomic():
            previous_private = request.event.private_testmode
            request.event.tickets_published = True
            request.event.settings.private_testmode_tickets = False
            request.event.private_testmode = request.event.settings.get(
                'private_testmode_talks',
                False,
                as_type=bool,
            )
            request.event.save()
            if previous_private != request.event.private_testmode:
                request.event.log_action(
                    'eventyay.event.private_testmode.deactivated',
                    user=actor,
                    auth=request.auth,
                    data={},
                )

        return Response(serialize_event_for_response(request), status=status.HTTP_200_OK)


class EventEnableManualPaymentView(APIView):
    permission_classes = (EventPermission,)
    permission = 'can_change_event_settings'

    @extend_schema(summary='Enable Manual Payment')
    def post(self, request, organizer, event):
        request.event.enable_plugin('eventyay.plugins.manualpayment')
        provider = ManualPayment(request.event)
        provider.settings.set('_enabled', True)
        if not provider.settings.get('public_name'):
            provider.settings.set('public_name', {'en': 'Manual payment'})
        if not provider.settings.get('checkout_description'):
            provider.settings.set(
                'checkout_description',
                {'en': 'Please follow the organizer instructions to complete payment.'},
            )
        if not provider.settings.get('pending_description'):
            provider.settings.set(
                'pending_description',
                {'en': 'Please follow the organizer instructions to complete payment.'},
            )

        return Response(
            {
                'provider': provider.identifier,
                'enabled': provider.is_enabled,
                'plugins': request.event.get_plugins(),
            },
            status=status.HTTP_200_OK,
        )


class CloneEventViewSet(viewsets.ModelViewSet):
    serializer_class = CloneEventSerializer
    queryset = Event.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    http_method_names = ['post']
    permission_classes = (CloneEventPermission,)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['organizer'] = self.request.organizer
        ctx['event'] = self.kwargs.get('event')
        return ctx

    def perform_create(self, serializer):
        inst = serializer.save(organizer=self.request.organizer)
        inst.log_action(
            'eventyay.event.added',
            user=self.request.user,
            auth=self.request.auth,
            data=merge_dicts(self.request.data, {'id': inst.pk}),
        )


with scopes_disabled():

    class SubEventFilter(FilterSet):
        is_past = django_filters.rest_framework.BooleanFilter(method='is_past_qs')
        is_future = django_filters.rest_framework.BooleanFilter(method='is_future_qs')
        ends_after = django_filters.rest_framework.IsoDateTimeFilter(method='ends_after_qs')
        modified_since = django_filters.IsoDateTimeFilter(field_name='last_modified', lookup_expr='gte')

        class Meta:
            model = SubEvent
            fields = ['active', 'event__live']

        def ends_after_qs(self, queryset, name, value):
            expr = Q(Q(date_to__isnull=True) & Q(date_from__gte=value)) | Q(
                Q(date_to__isnull=False) & Q(date_to__gte=value)
            )
            return queryset.filter(expr)

        def is_past_qs(self, queryset, name, value):
            expr = Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(
                Q(date_to__isnull=False) & Q(date_to__lt=now())
            )
            if value:
                return queryset.filter(expr)
            return queryset.exclude(expr)

        def is_future_qs(self, queryset, name, value):
            expr = Q(Q(date_to__isnull=True) & Q(date_from__gte=now())) | Q(
                Q(date_to__isnull=False) & Q(date_to__gte=now())
            )
            if value:
                return queryset.filter(expr)
            return queryset.exclude(expr)


class SubEventViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = SubEventSerializer
    queryset = SubEvent.objects.none()
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering = ('date_from',)
    ordering_fields = ('date_from', 'id')
    filterset_class = SubEventFilter
    write_permission = 'can_change_event_settings'

    def get_queryset(self):
        if getattr(self.request, 'event', None):
            qs = self.request.event.subevents.all()
        else:
            if isinstance(self.request.auth, (TeamAPIToken, Device)):
                events_qs = self.request.auth.get_events_with_any_permission()
            elif self.request.user.is_authenticated:
                events_qs = self.request.user.get_events_with_any_permission(self.request)
            else:
                events_qs = Event.objects.none()
            if getattr(self.request, 'organizer', None):
                events_qs = events_qs.filter(organizer=self.request.organizer)
            qs = SubEvent.objects.filter(event__in=events_qs)

        if getattr(self.request, 'organizer', None):
            qs = filter_qs_by_attr(qs, self.request)

        return qs.select_related('event').prefetch_related(
            'meta_values', 'meta_values__property', 'seat_category_mappings'
        )

    def perform_create(self, serializer):
        inst = serializer.save(event=self.request.event)
        inst.log_action(
            'eventyay.subevent.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data
        serializer.save()
        if serializer.data == original_data:
            return
        serializer.instance.log_action(
            'eventyay.subevent.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied(
                "The sub-event can not be deleted as it has already been used in orders. Please set 'active' to "
                'false instead to hide it from users.'
            )
        instance.log_action(
            'eventyay.subevent.deleted',
            user=self.request.user,
            auth=self.request.auth,
        )
        instance.delete()


class TaxRuleViewSet(ConditionalListView, viewsets.ModelViewSet):
    serializer_class = TaxRuleSerializer
    queryset = TaxRule.objects.none()
    write_permission = 'can_change_event_settings'

    def get_queryset(self):
        return self.request.event.tax_rules.all()

    def perform_create(self, serializer):
        inst = serializer.save(event=self.request.event)
        inst.log_action(
            'eventyay.event.taxrule.added',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_update(self, serializer):
        original_data = self.get_serializer(instance=serializer.instance).data
        serializer.save(event=self.request.event)
        if serializer.data == original_data:
            return
        serializer.instance.log_action(
            'eventyay.event.taxrule.changed',
            user=self.request.user,
            auth=self.request.auth,
            data=self.request.data,
        )

    def perform_destroy(self, instance):
        if not instance.allow_delete():
            raise PermissionDenied('This tax rule can not be deleted.')
        instance.log_action('eventyay.event.taxrule.deleted', user=self.request.user, auth=self.request.auth)
        instance.delete()


class EventSettingsView(views.APIView):
    permission = 'can_change_event_settings'
    permission_classes = (EventPermission,)

    def get(self, request, *args, **kwargs):
        s = EventSettingsSerializer(
            instance=request.event.settings,
            event=request.event,
            context={'request': request},
        )
        if 'explain' in request.GET:
            return Response(
                {
                    fname: {
                        'value': s.data[fname],
                        'label': getattr(field, '_label', fname),
                        'help_text': getattr(field, '_help_text', None),
                    }
                    for fname, field in s.fields.items()
                }
            )
        return Response(s.data)

    def patch(self, request, *wargs, **kwargs):
        s = EventSettingsSerializer(
            instance=request.event.settings,
            data=request.data,
            partial=True,
            event=request.event,
            context={'request': request},
        )
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            s.save()
            request.event.log_action(
                'eventyay.event.settings',
                user=request.user,
                auth=request.auth,
                data={k: v for k, v in s.validated_data.items()},
            )
        if any(p in s.changed_data for p in SETTINGS_AFFECTING_CSS):
            transaction.on_commit(lambda: regenerate_css.apply_async(args=(request.event.pk,)))
        s = EventSettingsSerializer(
            instance=request.event.settings,
            event=request.event,
            context={'request': request},
        )
        return Response(s.data)


def check_token_permission(token, permission_required):
    # Decode and validate the JWT token
    decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    # Check if user existed
    User.objects.get(email=decoded_data['email'])
    if decoded_data.get('has_perms') != permission_required:
        return False
    return True


@csrf_exempt
@require_POST
@scopes_disabled()
def talk_schedule_public(request, *args, **kwargs):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error('Authorization header missing or invalid')
        return JsonResponse({'status': 'Authorization header missing or invalid'}, status=403)

    token = auth_header.split(' ')[1]
    try:
        if not check_token_permission(token, 'base.edit_schedule'):
            return JsonResponse(
                {'status': 'User does not have permission to show schedule on menu'},
                status=403,
            )
        organizer = get_object_or_404(Organizer, slug=kwargs['organizer'])
        event = get_object_or_404(Event, slug=kwargs['event'], organizer=organizer)
        request_data = json.loads(request.body)
        is_show_schedule = bool(request_data.get('is_show_schedule'))
        flags = dict(event.feature_flags)
        flags['show_schedule'] = is_show_schedule
        event.feature_flags = flags
        event.settings.talk_schedule_public = is_show_schedule
        event.save(update_fields=['feature_flags'])
        return JsonResponse({'status': 'success'}, status=200)
    except jwt.ExpiredSignatureError:
        logger.error('Token has expired')
        return JsonResponse({'status': 'Token has expired'}, status=401)
    except jwt.InvalidTokenError:
        logger.error('Invalid token')
        return JsonResponse({'status': 'Invalid token'}, status=401)
    except User.DoesNotExist:
        logger.error('User not found for schedule-public token')
        return JsonResponse({'status': 'User not found'}, status=401)
    except json.JSONDecodeError:
        logger.error('Invalid JSON payload for schedule-public')
        return JsonResponse({'status': 'Invalid JSON payload'}, status=400)
    except Exception:
        logger.exception('Internal server error in talk_schedule_public')
        return JsonResponse({'status': 'Internal server error'}, status=500)


class CustomerOrderCheckView(APIView):
    """
    Check a customer's ticket / order for a given event.

    POST body (all fields optional, at least one must be supplied):
        {
            "email": "attendee@example.com",
            "code":  "ABCDE"
        }

    Responses:
        200  – order(s) found; returns a list of matching orders with their positions.
        400  – neither ``email`` nor ``code`` was supplied.
        404  – event not found, or no orders match the supplied criteria.
    """

    authentication_classes = ()
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        organizer_slug = kwargs.get('organizer')
        event_slug = kwargs.get('event')

        with scopes_disabled():
            organizer = get_object_or_404(Organizer, slug=organizer_slug)
            event = get_object_or_404(Event, slug=event_slug, organizer=organizer)

        email = request.data.get('email', '').strip()
        code = request.data.get('code', '').strip().upper()

        if not email and not code:
            return Response(
                {'detail': 'Please supply at least one of: email, code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from eventyay.base.models.orders import Order

        with scopes_disabled():
            qs = Order.objects.filter(event=event)
            if code:
                # Use exact (case-insensitive) match — normalization is for OCR/handwriting
                # and would corrupt codes like QXUG02 (2→Z gives QXUG0Z, no match)
                qs = qs.filter(code__iexact=code)
            if email:
                qs = qs.filter(email__iexact=email)

            orders = list(qs.prefetch_related('positions', 'positions__product'))

            result = []
            for order in orders:
                positions = []
                for pos in order.positions.all():
                    positions.append({
                        'id': pos.pk,
                        'product': str(pos.product.name),
                        'price': str(pos.price),
                        'attendee_name': pos.attendee_name_cached or '',
                        'attendee_email': pos.attendee_email or '',
                        'seat': str(pos.seat) if pos.seat else None,
                    })
                result.append({
                    'code': order.code,
                    'status': order.status,
                    'email': order.email or '',
                    'total': str(order.total),
                    'datetime': order.datetime.isoformat(),
                    'positions': positions,
                })

        if not result:
            return Response(
                {'detail': 'No orders found matching the supplied criteria.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(result, status=status.HTTP_200_OK)



class EventView(APIView):
    permission_classes = [ApiAccessRequiredPermission & EventPermissions]

    def get(self, request, **kwargs):
        return Response(RoomsEventSerializer(request.event).data)

    @transaction.atomic
    def patch(self, request, **kwargs):
        serializer = RoomsEventSerializer(request.event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(request.event.id)
        )
        return Response(serializer.data)


class EventThemeView(APIView):
    permission_classes = []

    def get(self, request, **kwargs):
        """
        Retrieve theme config of an event
        @param request: request obj
        @param kwargs: event_id
        @return: theme data of an event
        """
        try:
            event = get_object_or_404(Event, id=kwargs['event_id'])
            return Response(RoomsEventSerializer(event).data['config']['theme'])
        except KeyError:
            logger.error(
                'error happened when trying to get theme data of event: %s',
                kwargs['event_id'],
            )
            return Response(
                'error happened when trying to get theme data of event: ' + kwargs['event_id'],
                status=503,
            )


class CreateEventView(APIView):
    authentication_classes = []  # disables authentication
    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        payload = CreateEventView.get_payload_from_token(request)

        # check if user has permission to create event
        if payload.get('has_permission'):
            secret = get_random_string(length=64)
            config = {
                'JWT_secrets': [
                    {
                        'issuer': 'any',
                        'audience': 'eventyay',
                        'secret': secret,
                    }
                ]
            }

            titles = request.data.get('title') or {}
            locale = request.data.get('locale')

            title_values = [value for value in titles.values() if value]
            title_default = title_values[0] if title_values else ''

            title = titles.get(locale) or titles.get('en') or title_default

            traits_payload = request.data.get('traits') or {}
            if not isinstance(traits_payload, dict):
                raise ValidationError('Traits must be provided as an object.')

            attendee_trait_grants = traits_payload.get('attendee', '')
            if attendee_trait_grants and not isinstance(attendee_trait_grants, str):
                raise ValidationError('Attendee traits must be a string')

            trait_grants = {
                'admin': ['admin'],
                'attendee': ([attendee_trait_grants] if attendee_trait_grants else ['attendee']),
                'scheduleuser': [],
            }

            for trait_name, role_name in VIDEO_TRAIT_ROLE_MAP.items():
                trait_value = traits_payload.get(trait_name, '')
                if trait_value:
                    if not isinstance(trait_value, str):
                        raise ValidationError(f"Trait '{trait_name}' must be a string value.")
                    trait_grants[role_name] = [trait_value]

            # if event already exists, update it, otherwise create a new event
            event_id = request.data.get('id')
            domain_path = '{}{}/{}'.format(
                settings.DOMAIN_PATH,
                settings.BASE_PATH,
                request.data.get('id'),
            )
            try:
                if not event_id:
                    raise ValidationError('Event ID is required')
                if Event.objects.filter(id=event_id).exists():
                    event = Event.objects.get(id=event_id)
                    event.title = title
                    event.domain = domain_path
                    event.locale = request.data.get('locale') or 'en'
                    event.timezone = request.data.get('timezone') or 'UTC'
                    event.trait_grants = trait_grants
                    event.save()
                else:
                    event = Event.objects.create(
                        id=event_id,
                        title=title,
                        domain=domain_path,
                        locale=request.data.get('locale') or 'en',
                        timezone=request.data.get('timezone') or 'UTC',
                        config=config,
                        trait_grants=trait_grants,
                    )
                # Legacy eventyay-talk schedule connection is removed; video gets configured elsewhere.
                site_url = settings.SITE_URL
                protocol = get_protocol(site_url)
                event.domain = f'{protocol}://{domain_path}'
                return JsonResponse(model_to_dict(event, exclude=['roles']), status=201)
            except IntegrityError as e:
                logger.error(f'Database integrity error while saving event: {e}')
                return JsonResponse(
                    {'error': 'An event with this ID already exists or database constraint violated'},
                    status=400,
                )
            except ValidationError as e:
                logger.error(f'Validation error while saving event: {e}')
                return JsonResponse({'error': str(e)}, status=400)
            except Exception as e:
                logger.error(f'Unexpected error creating event: {e}')
                return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
        else:
            return JsonResponse(
                {'error': 'Event cannot be created due to missing permission'},
                status=403,
            )

    @staticmethod
    def get_payload_from_token(request):
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b'bearer':
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')
        try:
            payload = jwt.decode(auth_header[1], settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed('Invalid token')
        return payload


class UserFavouriteView(APIView):
    """DEPRECATED: Use per-submission favourite API instead.

    /api/v1/events/{event}/submissions/favourites/ (GET)
    /api/v1/events/{event}/submissions/{code}/favourite/ (POST/DELETE)
    /api/v1/events/{event}/submissions/favourites/merge/ (POST)
    """

    permission_classes = []

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        """
        Handle POST requests to add talks to the user's favourite list.
        Being called by eventyay-talk, authenticate by bearer token.
        """
        import warnings

        warnings.warn(
            'UserFavouriteView is deprecated, use per-submission favourite API',
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            talk_list = json.loads(request.body.decode())
            user_code = UserFavouriteView.get_uid_from_token(request, kwargs['event_id'])
            user = User.objects.get(token_id=user_code)
            if not user_code or not user:
                # user not created yet, no error should be returned
                logger.error('User not found for adding favourite talks.')
                return JsonResponse([], safe=False, status=200)
            if user.client_state is None:
                # If it's None, create a new dictionary with schedule.favs field
                user.client_state = {'schedule': {'favs': talk_list}}
            else:
                # If client_state is not None, check if 'schedule' field exists
                if 'schedule' not in user.client_state:
                    # If 'schedule' field doesn't exist, create it
                    user.client_state['schedule'] = {'favs': talk_list}
                else:
                    # If 'schedule' field exists, update the 'favs' field
                    user.client_state['schedule']['favs'] = talk_list
            user.save()
            return JsonResponse(talk_list, safe=False, status=200)
        except Exception as e:
            logger.error(
                'error happened when trying to add fav talks: %s',
                kwargs['event_id'],
            )
            logger.error(e)
            # Since this is called from background so no error should be returned
            return JsonResponse([], safe=False, status=200)

    @staticmethod
    def get_uid_from_token(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        auth_header = get_authorization_header(request).split()
        if auth_header and auth_header[0].lower() == b'bearer':
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')
        token_decode = event.decode_token(token=auth_header[1])
        return token_decode.get('uid')


"""Legacy eventyay-talk integration helpers (schedule export proxy and schedule_update push endpoint)

These were used for connecting a talk system instance as a schedule source. The video SPA now
connects directly, so the legacy endpoints have been removed.
"""


@api_view(http_method_names=['POST'])
@permission_classes([UserDeletePermissions])
def delete_user(request, **kwargs):
    """POST endpoint to soft-delete a user.

    This endpoint is called with a single POST parameter, 'user_id'."""
    user_id = request.data.get('user_id')
    token_id = request.data.get('token_id')
    if not user_id and not token_id:
        return Response('Missing user ID.', status=400)
    if user_id and token_id:
        return Response('Ambiguous user ID.', status=400)

    user = None
    with suppress(exceptions.ValidationError):  # raised when user_id isn't a uid
        if user_id:
            user = User.objects.filter(id=user_id, deleted=False).first()
        elif token_id:
            user = User.objects.filter(token_id=token_id, deleted=False).first()
    if not user:
        return Response(status=404)

    user.soft_delete()
    return Response(status=204)
