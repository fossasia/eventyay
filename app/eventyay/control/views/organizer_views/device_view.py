import json
import os

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from eventyay.api.auth.devicesecurity import DEVICE_SECURITY_PROFILES
from eventyay.base.models.checkin import Checkin
from eventyay.base.models.devices import Device, generate_initialization_token
from eventyay.base.models.log import LogEntry
from eventyay.control.forms.organizer_forms.device_form import DeviceForm
from eventyay.control.permissions import OrganizerPermissionRequiredMixin
from eventyay.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)


def _device_event_navigation_context(request, *, current_label=None):
    slug = request.GET.get('from_event') or request.session.get('device_return_event')
    if not slug:
        return {}
    event = request.organizer.events.filter(slug=slug).first()
    if not event:
        return {}
    request.session['device_return_event'] = slug
    devices_url = reverse(
        'eventyay_common:organizer.devices',
        kwargs={'organizer': request.organizer.slug},
    )
    ctx = {
        'return_event_slug': slug,
        'return_checkinlists_url': reverse(
            'control:event.orders.checkinlists',
            kwargs={'organizer': request.organizer.slug, 'event': slug},
        ),
        'organizer_devices_url': f'{devices_url}?from_event={slug}',
    }
    if current_label is not None:
        ctx['device_nav_current'] = current_label
    return ctx


def _device_return_checkinlists_context(request, **kwargs):
    return _device_event_navigation_context(request, **kwargs)


def _devices_success_url(request):
    url = reverse(
        'eventyay_common:organizer.devices',
        kwargs={'organizer': request.organizer.slug},
    )
    slug = request.session.get('device_return_event')
    if slug and request.organizer.events.filter(slug=slug).exists():
        return f'{url}?from_event={slug}'
    return url


def _device_security_profiles_context():
    return [
        {
            'name': profile.verbose_name,
            'usage': profile.usage_description,
        }
        for profile in DEVICE_SECURITY_PROFILES.values()
        if getattr(profile, 'usage_description', None)
    ]


class DeviceCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = DeviceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['device_security_profiles'] = _device_security_profiles_context()
        ctx.update(_device_return_checkinlists_context(self.request, current_label=_('Connect a new device')))
        return ctx

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.devices.connect',
            kwargs={'organizer': self.request.organizer.slug, 'device': self.object.pk},
        )

    def form_valid(self, form):
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action(
            'eventyay.device.created',
            user=self.request.user,
            data={
                k: getattr(self.object, k) if k not in ('limit_events', 'limit_checkin_lists') else [x.id for x in getattr(self.object, k).all()]
                for k in form.changed_data
            },
        )
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class DeviceListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = Device
    template_name = 'pretixcontrol/organizers/devices.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'devices'

    def get_queryset(self):
        return self.request.organizer.devices.prefetch_related('limit_events').order_by('revoked', '-device_id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_device_return_checkinlists_context(self.request))
        return ctx


class DeviceLogView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/organizers/device_logs.html'
    permission = 'can_change_organizer_settings'
    model = LogEntry
    context_object_name = 'logs'
    paginate_by = 20

    @cached_property
    def device(self):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['device'] = self.device
        ctx.update(
            _device_return_checkinlists_context(self.request, current_label=_('Device logs'))
        )
        return ctx

    def get_queryset(self):
        qs = (
            LogEntry.objects.filter(device_id=self.device)
            .select_related(
                'user',
                'content_type',
                'api_token',
                'oauth_application',
            )
            .prefetch_related('device', 'event')
            .order_by('-datetime')
        )
        return qs


class DeviceUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'
    form_class = DeviceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['device_security_profiles'] = _device_security_profiles_context()
        ctx.update(
            _device_return_checkinlists_context(self.request, current_label=self.object.name)
        )
        return ctx

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.devices',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action(
                'eventyay.device.changed',
                user=self.request.user,
                data={
                    k: getattr(self.object, k) if k not in ('limit_events', 'limit_checkin_lists') else [x.id for x in getattr(self.object, k).all()]
                    for k in form.changed_data
                },
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class DeviceConnectView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_connect.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'ajax' in request.GET:
            return JsonResponse({'initialized': bool(self.object.initialized)})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        had_active_session = bool(self.object.api_token and self.object.initialized)

        self.object.initialization_token = generate_initialization_token()
        self.object.api_token = None
        self.object.initialized = None
        self.object.revoked = False
        self.object.save(
            update_fields=['initialization_token', 'api_token', 'initialized', 'revoked']
        )
        self.object.log_action(
            'eventyay.device.setup_token_reset',
            user=self.request.user,
            data={'had_active_session': had_active_session},
        )
        if had_active_session:
            messages.success(
                request,
                _(
                    'A new setup code has been generated. This device has been disconnected and must '
                    'be registered again with the updated QR code.'
                ),
            )
        else:
            messages.success(request, _('A new setup code has been generated. Scan or enter the updated QR code.'))
        return redirect(
            reverse(
                'eventyay_common:organizer.devices.connect',
                kwargs={'organizer': self.request.organizer.slug, 'device': self.object.pk},
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _device_return_checkinlists_context(self.request, current_label=self.object.name)
        )
        site_url = (
            self.request.build_absolute_uri('/').rstrip('/')
            if settings.DEBUG
            else settings.SITE_URL.rstrip('/')
        )
        checkin_host = self.request.get_host().split(':')[0]
        if os.environ.get('EVY_NPM_DEV') == '1':
            checkin_app_url = f'http://{checkin_host}:8085/'
        else:
            checkin_app_url = 'https://access.eventyay.com/'
        ctx['checkin_app_url'] = checkin_app_url
        ctx['checkin_app_is_dev'] = os.environ.get('EVY_NPM_DEV') == '1'
        ctx['registration_site_url'] = site_url
        ctx['qrdata'] = json.dumps(
            {
                'handshake_version': 1,
                'url': site_url,
                'token': self.object.initialization_token,
            }
        )
        return ctx


class DeviceRevokeView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_revoke.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _device_return_checkinlists_context(self.request, current_label=_('Revoke access'))
        )
        ctx['devices_url'] = _devices_success_url(self.request)
        return ctx

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.api_token:
            messages.success(request, _('This device currently does not have access.'))
            return redirect(_devices_success_url(request))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.revoked = True
        self.object.save()
        self.object.log_action('eventyay.device.revoked', user=self.request.user)
        messages.success(request, _('Access for this device has been revoked.'))
        return redirect(_devices_success_url(request))


class DeviceRevokeAllView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/organizers/device_revoke_all.html'
    permission = 'can_change_organizer_settings'

    def _devices_qs(self):
        return self.request.organizer.devices.all()

    def _success_url(self):
        return _devices_success_url(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['device_count'] = self._devices_qs().count()
        ctx.update(
            _device_return_checkinlists_context(
                self.request, current_label=_('Revoke and remove all devices')
            )
        )
        ctx['devices_url'] = self._success_url()
        return ctx

    def get(self, request, *args, **kwargs):
        if not self._devices_qs().exists():
            messages.success(self.request, _('There are no connected devices to revoke and remove.'))
            return redirect(self._success_url())
        return super().get(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        device_ids = list(self._devices_qs().values_list('id', flat=True))
        if not device_ids:
            messages.success(self.request, _('There are no connected devices to revoke and remove.'))
            return redirect(self._success_url())

        Checkin.objects.filter(device_id__in=device_ids).update(device=None)
        LogEntry.all.filter(device_id__in=device_ids).update(device=None)
        self._devices_qs().filter(id__in=device_ids).delete()

        self.request.organizer.log_action(
            'eventyay.device.revoked_all',
            user=self.request.user,
            data={'count': len(device_ids)},
        )
        messages.success(self.request, _('All connected devices have been revoked and removed permanently.'))
        return redirect(self._success_url())
