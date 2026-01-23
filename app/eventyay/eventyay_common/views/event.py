import datetime as dt
import logging
from datetime import datetime, timedelta
from datetime import timezone as tz
from enum import StrEnum
from urllib.parse import urlparse

import jwt
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, F, Max, Min, Prefetch, Q, Sum, When, IntegerField
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import get_current_timezone_name
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django_scopes import scope
from pytz import timezone
from rest_framework import views
from django.views import View
from django.apps import apps

from eventyay.base.forms import SafeSessionWizardView
from eventyay.base.i18n import language
from eventyay.base.models import Event, EventMetaValue, Organizer, Quota
from eventyay.base.services import tickets
from eventyay.base.settings import SETTINGS_AFFECTING_CSS
from eventyay.presale.style import regenerate_css
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.control.forms.event import EventWizardBasicsForm, EventWizardFoundationForm
from eventyay.control.forms.filter import EventFilterForm
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views import PaginationMixin, UpdateView
from eventyay.control.views.event import DecoupleMixin, EventSettingsViewMixin, EventPlugins as ControlEventPlugins
from eventyay.control.views.product import MetaDataEditorMixin
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.eventyay_common.utils import (
    EventCreatedFor,
    check_create_permission,
    encode_email,
    generate_token,
)
from eventyay.orga.forms.event import EventFooterLinkFormset, EventHeaderLinkFormset
from eventyay.eventyay_common.video.permissions import collect_user_video_traits
from eventyay.helpers.plugin_enable import is_video_enabled
from ..forms.event import EventUpdateForm

logger = logging.getLogger(__name__)

class EventList(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'eventyay_common/events/index.html'
    ordering_fields = [
        'name',
        'slug',
        'organizer',
        'date_from',
        'date_to',
        'total_quota',
        'live',
        'order_from',
        'order_to',
    ]

    def get_queryset(self):
        query_set = self.request.user.get_events_with_any_permission(self.request).prefetch_related(
            'organizer',
            '_settings_objects',
            'organizer___settings_objects',
            'organizer__meta_properties',
            Prefetch(
                'meta_values',
                EventMetaValue.objects.select_related('property'),
                to_attr='meta_values_cached',
            ),
        )

        query_set = query_set.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
            total_quota=Sum(
                Case(When(quotas__subevent__isnull=True, then='quotas__size'), default=0, output_field=IntegerField())
            ),
        ).annotate(
            order_from=Coalesce('min_from', 'date_from'),
            order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
        )

        ordering = self.request.GET.get('ordering')
        if ordering and ordering.lstrip('-') in self.ordering_fields:
            if ordering == 'date_from':
                query_set = query_set.order_by('order_from')
            elif ordering == '-date_from':
                query_set = query_set.order_by('-order_from')
            elif ordering == 'date_to':
                query_set = query_set.order_by('order_to')
            elif ordering == '-date_to':
                query_set = query_set.order_by('-order_to')
            else:
                query_set = query_set.order_by(ordering)
        else:
            query_set = query_set.order_by('-date_from')

        query_set = query_set.prefetch_related(
            Prefetch(
                'quotas',
                queryset=Quota.objects.filter(subevent__isnull=True).annotate(s=Coalesce(F('size'), 0)).order_by('-s'),
                to_attr='first_quotas',
            )
        )

        if self.filter_form.is_valid():
            query_set = self.filter_form.filter_qs(query_set)
        return query_set

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        quotas = []
        for s in ctx['events']:
            s.plugins_array = s.get_plugins()
            s.first_quotas = s.first_quotas[:4]
            quotas += list(s.first_quotas)

        qa = QuotaAvailability(early_out=False)
        for q in quotas:
            qa.queue(q)
        qa.compute()

        for q in quotas:
            q.cached_avail = qa.results[q]
            q.cached_availability_paid_orders = qa.count_paid_orders.get(q, 0)
            if q.size is not None:
                q.percent_paid = min(
                    100,
                    (round(q.cached_availability_paid_orders / q.size * 100) if q.size > 0 else 100),
                )
        return ctx

    @cached_property
    def filter_form(self):
        return EventFilterForm(data=self.request.GET, request=self.request)


class EventCreateView(SafeSessionWizardView):
    form_list = [
        ('foundation', EventWizardFoundationForm),
        ('basics', EventWizardBasicsForm),
    ]
    templates = {
        'foundation': 'eventyay_common/events/create_foundation.html',
        'basics': 'eventyay_common/events/create_basics.html',
    }
    condition_dict = {}

    def get_form_initial(self, step):
        initial_form = super().get_form_initial(step)
        request_user = self.request.user
        request_get = self.request.GET

        if step == 'foundation':
            initial_form['is_video_creation'] = True
            initial_form['locales'] = ['en']
            initial_form['content_locales'] = ['en']
            initial_form['create_for'] = EventCreatedFor.BOTH
            if 'organizer' in request_get:
                try:
                    queryset = Organizer.objects.all()
                    if not request_user.has_active_staff_session(self.request.session.session_key):
                        queryset = queryset.filter(
                            id__in=request_user.teams.filter(can_create_events=True).values_list('organizer', flat=True)
                        )
                    initial_form['organizer'] = queryset.get(slug=request_get.get('organizer'))
                except Organizer.DoesNotExist:
                    pass

        elif step == 'basics':
            initial_form['locale'] = 'en'

            # Set default dates: 3 months from now, 9 AM to 5 PM in user's timezone
            user_tz = timezone(get_current_timezone_name())
            now = user_tz.localize(datetime.now())
            default_start = now + timedelta(days=90)
            default_start = default_start.replace(hour=9, minute=0, second=0, microsecond=0)
            default_end = default_start.replace(hour=17, minute=0, second=0, microsecond=0)

            initial_form['date_from'] = default_start
            initial_form['date_to'] = default_end

            # Set default timezone to user's system timezone (consistent with manual entry)
            initial_form['timezone'] = get_current_timezone_name()

        return initial_form

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        context['create_for'] = self.storage.extra_data.get('create_for', EventCreatedFor.BOTH)
        context['has_organizer'] = self.request.user.teams.filter(can_create_events=True).exists()
        if self.steps.current == 'basics':
            context['organizer'] = self.get_cleaned_data_for_step('foundation').get('organizer')
        context['event_creation_for_choice'] = {e.name: e.value for e in EventCreatedFor}
        return context

    def render(self, form=None, **kwargs):
        if self.steps.current == 'basics' and 'create_for' in self.request.POST:
            self.storage.extra_data['create_for'] = self.request.POST.get('create_for')
        if self.steps.current != 'foundation':
            form_data = self.get_cleaned_data_for_step('foundation')
            if form_data is None:
                return self.render_goto_step('foundation')

        return super().render(form, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = {
            'user': self.request.user,
            'session': self.request.session,
        }
        if step != 'foundation':
            form_data = self.get_cleaned_data_for_step('foundation')
            if form_data is None:
                form_data = {
                    'organizer': Organizer(slug='_nonexisting'),
                    'has_subevents': False,
                    'locales': ['en'],
                    'is_video_creation': True,
                }
            kwargs.update(form_data)
        return kwargs

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def done(self, form_list, form_dict, **kwargs):
        foundation_data = self.get_cleaned_data_for_step('foundation')
        basics_data = self.get_cleaned_data_for_step('basics')

        create_for = self.storage.extra_data.get('create_for')

        self.request.organizer = foundation_data['organizer']
        has_permission = check_create_permission(self.request)
        final_is_video_creation = foundation_data.get('is_video_creation', True) and has_permission

        with transaction.atomic(), language(basics_data['locale']):
            event = form_dict['basics'].instance
            event.organizer = foundation_data['organizer']

            plugins_default = settings.PRETIX_PLUGINS_DEFAULT
            if isinstance(plugins_default, str):
                default_plugins = [p.strip() for p in plugins_default.split(',') if p.strip()]
            else:
                default_plugins = list(plugins_default or [])

            ticketing_plugins = [
                'eventyay.plugins.ticketoutputpdf',
                'eventyay.plugins.banktransfer',
                'eventyay.plugins.manualpayment',
            ]

            installed_apps = {app.name for app in apps.get_app_configs()}

            for plugin_name in ['eventyay_stripe', 'eventyay_paypal']:
                if plugin_name in installed_apps:
                    ticketing_plugins.append(plugin_name)

            all_plugins = list(dict.fromkeys(default_plugins + ticketing_plugins))
            event.plugins = ','.join(all_plugins)

            event.has_subevents = foundation_data['has_subevents']
            event.is_video_creation = final_is_video_creation
            event.testmode = True
            form_dict['basics'].save()

            with scope(organizer=event.organizer):
                event.checkin_lists.create(name=_('Default'), all_products=True)
            event.set_defaults()
            event.settings.set('timezone', basics_data['timezone'])
            event.settings.set('locale', basics_data['locale'])
            event.settings.set('locales', foundation_data['locales'])
            content_locales = foundation_data.get('content_locales') or foundation_data['locales']
            event.settings.set('content_locales', content_locales)
            # Persist timezone on the event model as well so downstream consumers see the updated value
            event.timezone = basics_data['timezone']
            event.save(update_fields=['timezone'])
            
            # Save imprint_url to settings (consistent with EventCommonSettingsForm)
            if basics_data.get('imprint_url'):
                event.settings.set('imprint_url', basics_data['imprint_url'])

            # Use the selected create_for option, but ensure smart defaults work for all
            create_for = self.storage.extra_data.get('create_for', EventCreatedFor.BOTH)
            event.settings.set('create_for', create_for)

            # Smart defaults work for all event types
            if create_for in [EventCreatedFor.BOTH, EventCreatedFor.TICKET, EventCreatedFor.TALK]:
                event_dict = {
                    'organiser_slug': event.organizer.slug,
                    'name': event.name.data,
                    'slug': event.slug,
                    'is_public': event.live,
                    'date_from': str(event.date_from),
                    'date_to': str(event.date_to),
                    'timezone': str(basics_data.get('timezone')),
                    'locale': event.settings.locale,
                    'locales': event.settings.locales,
                    'content_locales': content_locales,
                    'is_video_creation': final_is_video_creation,
                }

            event.log_action(
                    action='eventyay.event.added',
                    user=self.request.user,
                )

        return redirect(
            reverse(
                'eventyay_common:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
        )


class EventUpdate(
    DecoupleMixin,
    EventSettingsViewMixin,
    EventPermissionRequiredMixin,
    MetaDataEditorMixin,
    UpdateView,
):
    model = Event
    form_class = EventUpdateForm
    template_name = 'eventyay_common/event/settings.html'
    permission = 'can_change_event_settings'

    class ValidComponentAction(StrEnum):
        ENABLE = 'enable'

    @cached_property
    def object(self) -> Event:
        return self.request.event

    def get_object(self, queryset=None) -> Event:
        return self.object

    @cached_property
    def sform(self):
        return EventCommonSettingsForm(
            obj=self.object,
            prefix='settings',
            data=self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
        )

    @cached_property
    def header_links_formset(self):
        return EventHeaderLinkFormset(
            self.request.POST if self.request.method == 'POST' else None,
            event=self.object,
            prefix='header-links',
            instance=self.object,
        )

    @cached_property
    def footer_links_formset(self):
        return EventFooterLinkFormset(
            self.request.POST if self.request.method == 'POST' else None,
            event=self.object,
            prefix='footer-links',
            instance=self.object,
        )

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        context['header_links_formset'] = self.header_links_formset
        context['footer_links_formset'] = self.footer_links_formset
        context['is_video_enabled'] = is_video_enabled(self.object)
        context['is_talk_event_created'] = False
        if (
            self.object.settings.create_for == EventCreatedFor.BOTH
            or self.object.settings.talk_schedule_public is not None
        ):
            # Ignore case Event is created only for Talk as it not enable yet.
            context['is_talk_event_created'] = True
        return context

    @transaction.atomic
    def form_valid(self, form):
        self._save_decoupled(self.sform)
        self.sform.save()
        self.header_links_formset.save()
        self.footer_links_formset.save()
        # Keep event model timezone in sync with settings
        if 'timezone' in self.sform.cleaned_data:
            self.object.timezone = self.sform.cleaned_data['timezone']
            self.object.save(update_fields=['timezone'])
        form.instance.update_language_configuration(
            locales=self.sform.cleaned_data.get('locales'),
            content_locales=self.sform.cleaned_data.get('content_locales'),
            default_locale=self.sform.cleaned_data.get('locale'),
        )

        tickets.invalidate_cache.apply_async(kwargs={'event': self.request.event.pk})

        if self.sform.has_changed() and any(p in self.sform.changed_data for p in SETTINGS_AFFECTING_CSS):
            transaction.on_commit(lambda: regenerate_css.apply_async(args=(self.request.event.pk,)))
            messages.success(
                self.request,
                _(
                    'Your changes have been saved. Please note that it can '
                    'take a short period of time until your changes become '
                    'active.'
                ),
            )

        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:event.update',
            kwargs={
                'organizer': self.object.organizer.slug,
                'event': self.object.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pass necessary kwargs to the EventUpdateForm in common
        is_staff_session = self.request.user.has_active_staff_session(self.request.session.session_key)
        kwargs['change_slug'] = is_staff_session
        # TODO: Re-enable custom domain when unified system is stable
        # kwargs['domain'] = is_staff_session
        return kwargs

    def enable_talk_system(self, request: HttpRequest) -> bool:
        """
        Enable talk system for this event if it has not been created yet.
        """
        action = request.POST.get('enable_talk_system', '').lower()
        if action != self.ValidComponentAction.ENABLE:
            return False

        if not check_create_permission(self.request):
            messages.error(self.request, _('You do not have permission to perform this action.'))
            return False


        return True

    def enable_video_system(self, request: HttpRequest) -> bool:
        """
        Enable video system for this event if it has not been created yet.
        """
        action = request.POST.get('enable_video_system', '').lower()
        if action != self.ValidComponentAction.ENABLE:
            return False

        if not check_create_permission(self.request):
            messages.error(self.request, _('You do not have permission to perform this action.'))
            return False

        return True

    def post(self, request, *args, **kwargs):
        if self.enable_talk_system(request):
            return redirect(self.get_success_url())

        if self.enable_video_system(request):
            return redirect(self.get_success_url())

        form = self.get_form()
        has_formset_changes = self.header_links_formset.has_changed() or self.footer_links_formset.has_changed()
        if form.changed_data or self.sform.changed_data or has_formset_changes:
            form.instance.sales_channels = ['web']
            if (
                form.is_valid()
                and self.sform.is_valid()
                and self.header_links_formset.is_valid()
                and self.footer_links_formset.is_valid()
            ):
                zone = timezone(self.sform.cleaned_data['timezone'])
                event = form.instance
                event.date_from = self.reset_timezone(zone, event.date_from)
                event.date_to = self.reset_timezone(zone, event.date_to)
                return self.form_valid(form)
            else:
                messages.error(
                    self.request,
                    _('We could not save your changes. See below for details.'),
                )
                return self.form_invalid(form)
        else:
            messages.warning(self.request, _("You haven't made any changes."))
            return HttpResponseRedirect(self.request.path)

    @staticmethod
    def reset_timezone(tz, dt):
        return tz.localize(dt.replace(tzinfo=None)) if dt is not None else None


class EventPlugins(ControlEventPlugins):
    template_name = 'eventyay_common/event/plugins.html'

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:event.plugins',
            kwargs={
                'organizer': self.get_object().organizer.slug,
                'event': self.get_object().slug,
            },
        )


class VideoAccessAuthenticator(View):
    def get(self, request, *args, **kwargs):
        """
        Check if the video configuration is complete, the plugin is enabled, and the user has permission to modify the event settings.
        If configuration is missing, automatically set it up. Then generate a token and redirect to video system.
        @param request: user request
        @param args: arguments
        @param kwargs: keyword arguments
        @return: redirect to the video system
        """
        has_staff_video_access = self._has_staff_video_access()
        video_traits = self._collect_user_video_traits()

        # Auto-setup video configuration if missing
        self._ensure_video_configuration()

        # Generate token and include in url to video system
        token_traits = self._build_token_traits(has_staff_video_access, video_traits)
        return redirect(self.generate_token_url(request, token_traits))

    def _has_staff_video_access(self) -> bool:
        request = self.request
        return request.user.has_active_staff_session(request.session.session_key)

    def _collect_user_video_traits(self):
        permission_set = self.request.user.get_event_permission_set(self.request.organizer, self.request.event)
        return collect_user_video_traits(self.request.event.slug, permission_set)

    def _build_token_traits(self, has_staff_video_access: bool, video_traits):
        """
        Build the list of traits to include in the JWT token.
        - All users get 'attendee' trait for basic access
        - Users get specific video permission traits based on their team permissions
        - Only staff users (superuser, is_staff, or active staff session) get 'admin' trait
        """
        traits = ['attendee']
        traits.extend(video_traits)
        # Only add 'admin' trait for staff users - this grants full admin access
        # Regular organizers should NOT get 'admin' trait, only specific video permission traits
        if has_staff_video_access:
            organizer_trait = f'eventyay-video-event-{self.request.event.slug}-organizer'
            traits.extend(['admin', organizer_trait])
        # Deduplicate while preserving order
        seen = set()
        deduped_traits = []
        for trait in traits:
            if trait and trait not in seen:
                seen.add(trait)
                deduped_traits.append(trait)
        return deduped_traits

    def _ensure_video_configuration(self):
        """
        Ensure video configuration is set up properly, similar to admin token flow
        """
        event = self.request.event
        request = self.request

        # Ensure JWT configuration exists
        if not event.config or not event.config.get("JWT_secrets"):
            from django.utils.crypto import get_random_string

            secret = get_random_string(length=64)
            event.config = {
                "JWT_secrets": [
                    {
                        "issuer": "any",
                        "audience": "eventyay",
                        "secret": secret,
                    }
                ]
            }
            event.save()

        # Get or use existing JWT secret
        jwt_config = event.config["JWT_secrets"][0]
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]

        # Setup video plugin settings for the video frontend
        # Set each video config setting individually if missing
        if not event.settings.venueless_secret:
            event.settings.venueless_secret = secret
        if not event.settings.venueless_issuer:
            event.settings.venueless_issuer = issuer
        if not event.settings.venueless_audience:
            event.settings.venueless_audience = audience
        def build_video_url(host=None):
            scheme = 'https' if request.is_secure() else 'http'
            base_host = host or request.get_host()
            return f"{scheme}://{base_host}{event.urls.video_base}"

        if not event.settings.venueless_url:
            event.settings.venueless_url = build_video_url()
            logger.info(
                "Initialized video_url for event %s to %s",
                event.slug,
                event.settings.venueless_url,
            )

        # If the saved URL points to a different host than the current request (e.g., prod domain),
        # adjust it to the current host so local development goes to localhost.
        try:
            saved = urlparse(str(event.settings.venueless_url))
            current_host = request.get_host()
            if saved.netloc and saved.netloc != current_host:
                event.settings.venueless_url = build_video_url(current_host)
                logger.info(
                    "Adjusted video_url for event %s to %s",
                    event.slug,
                    event.settings.venueless_url,
                )
        except Exception:
            logger.exception(
                "Failed to parse video_url for event %s; falling back to current host.",
                event.slug,
            )
            event.settings.venueless_url = build_video_url()

        # Video is integrated; do not toggle event plugins here.

    def generate_token_url(self, request, traits):
        uid_token = encode_email(request.user.email)
        iat = datetime.now(tz.utc)
        exp = iat + dt.timedelta(days=1)
        payload = {
            'iss': self.request.event.settings.venueless_issuer,
            'aud': self.request.event.settings.venueless_audience,
            'exp': exp,
            'iat': iat,
            'uid': uid_token,
            'traits': traits,
        }
        token = jwt.encode(payload, self.request.event.settings.venueless_secret, algorithm='HS256')
        base_url = self.request.event.settings.venueless_url
        return '{}/#token={}'.format(base_url, token).replace('//#', '/#')


class EventSearchView(views.APIView):
    def get(self, request):
        query = request.GET.get('query', '')
        events = (
            Event.objects.filter(Q(name__icontains=query) | Q(slug__icontains=query))
            .order_by('name')
            .select_related('organizer')[:10]
        )

        results = []
        for event in events:
            if request.user.has_event_permission(event.organizer, event, 'can_view_orders', request=request):
                results.append({'name': event.name, 'slug': event.slug, 'organizer': event.organizer.slug})

        return JsonResponse(results, safe=False)
