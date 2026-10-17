import copy
import datetime
import json

import icalendar
import jwt
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from eventyay.base.models.auth import User
from django.db import transaction
from django.db.models import Count, F, Max, OuterRef, Subquery
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    BBBCall,
    BBBServer,
    SystemLog,
    JanusServer,
    JitsiServer,
    LoungeMeshServer,
    TurnServer,
    Event,
    StreamSchedule,
)

from eventyay.base.models.event import EventPlannedUsage as PlannedUsage
from eventyay.base.services.bbb import get_url
from eventyay.control.forms.server_management import (
    BBBMoveRoomForm,
    BBBServerForm,
    JanusServerForm,
    JitsiServerForm,
    LoungeMeshServerForm,
    PlannedUsageFormSet,
    ProfileForm,
    SignupForm,
    TurnServerForm,
    UserForm,
    EventForm,
    VideoStreamScheduleForm,
    VideoStreamingSelectionForm,
)
from eventyay.base.services.event import notify_event_change
from eventyay.base.services.room import broadcast_stream_change
from eventyay.base.models.log import LogEntry
from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, emit_logged_action, log_event
from eventyay.base.settings import (
    GlobalSettingsObject,
    SUPPORTED_VIDEO_PROVIDERS,
    get_video_provider_visibility,
)
from eventyay.helpers.compat import CompatDeleteView
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.tasks import clear_event_data
from eventyay.control.video.admin_dashboard import get_video_server_config


def _admin_log_entry(**kwargs):
    entry = LogEntry.objects.create(**kwargs)
    obj = kwargs.get('content_object')
    user = kwargs.get('user')
    data = kwargs.get('data')
    if not isinstance(data, dict):
        data = None
    try:
        emit_logged_action(
            kwargs.get('action_type'),
            object_id=getattr(obj, 'pk', None),
            user_id=getattr(user, 'pk', None),
            is_orga_action=True,
            model=type(obj).__name__ if obj is not None else None,
            data=data,
        )
    except Exception:
        pass
    return entry


class SuperuserBase(AdministratorPermissionRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class UserList(SuperuserBase, ListView):
    template_name = "control/user_list.html"
    queryset = User.objects.all()
    context_object_name = "users"


class UserUpdate(SuperuserBase, UpdateView):
    template_name = "control/user_update.html"
    queryset = User.objects.all()
    context_object_name = "users"
    form_class = UserForm
    success_url = "/admin/video/users/"

    def form_valid(self, form):
        _admin_log_entry(
            content_object=self.object,
            user=self.request.user,
            action_type="user.changed",
            data={"changed_keys": form.changed_data},
        )
        return super().form_valid(form)


class SignupView(SuperuserBase, FormView):
    template_name = "registration/register.html"
    form_class = SignupForm

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("The user has been created successfully, they can now log in."),
        )
        return redirect("/admin/video/")


class ProfileView(AdministratorPermissionRequiredMixin, FormView):
    template_name = "control/profile.html"
    form_class = ProfileForm
    success_url = "/admin/video/auth/profile/"

    def form_valid(self, form):
        _admin_log_entry(
            content_object=self.request.user,
            user=self.request.user,
            action_type="profile.changed",
            data={"changed_keys": form.changed_data},
        )
        form.save()
        update_session_auth_hash(self.request, self.request.user)
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["instance"] = self.request.user
        return result


class VideoSettings(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = "control/video_settings.html"

    @cached_property
    def streaming_selection(self):
        """Validate the selected event and stream identifiers."""
        form = VideoStreamingSelectionForm(self.request.GET)
        with scopes_disabled():
            if not form.is_valid():
                raise Http404
        return form

    @cached_property
    def streaming_instance(self):
        """Load a stream only from the explicitly selected event."""
        event = self.streaming_selection.cleaned_data['event']
        stream_id = self.streaming_selection.cleaned_data.get('stream')
        if not stream_id:
            return None
        if not event:
            raise Http404
        with scope(event=event):
            return get_object_or_404(
                StreamSchedule.objects.select_related('room', 'room__event'),
                pk=stream_id, room__event=event,
            )

    def get_context_data(self, **kwargs):
        """Group provider settings and the selected event's streaming configuration."""
        ctx = super().get_context_data(**kwargs)
        bbb_qs = BBBServer.objects.select_related("event_exclusive").prefetch_related("organizers", "events").order_by("url")
        janus_qs = JanusServer.objects.select_related("event_exclusive").prefetch_related("organizers", "events").order_by("url")
        jitsi_qs = JitsiServer.objects.select_related("event_exclusive").prefetch_related("organizers", "events").order_by("url")
        turn_qs = TurnServer.objects.select_related("event_exclusive").prefetch_related("organizers", "events").order_by("hostname")
        loungemesh_qs = LoungeMeshServer.objects.select_related("event_exclusive").prefetch_related("organizers", "events").order_by("url")

        ctx["bbb_servers"] = bbb_qs
        ctx["janus_servers"] = janus_qs
        ctx["jitsi_servers"] = jitsi_qs
        ctx["turn_servers"] = turn_qs
        ctx["loungemesh_servers"] = loungemesh_qs

        # Provider visibility and status for the General tab
        visibility = get_video_provider_visibility()
        ctx["provider_visibility"] = visibility
        ctx["providers"] = [
            {
                "id": "bbb",
                "name": _("BigBlueButton"),
                "icon": "fa-graduation-cap",
                "badge": f"{bbb_qs.filter(active=True).count()} / {bbb_qs.count()} " + str(_("servers")),
                "description": _("Classroom and lecture conferencing system. Best for workshops, breakout sessions, and structured presentations."),
                "enabled": visibility.get("bbb", {}).get("organizer", True) and visibility.get("bbb", {}).get("attendee", True),
                "organizer": visibility.get("bbb", {}).get("organizer", True),
                "attendee": visibility.get("bbb", {}).get("attendee", True),
                "server_tab": "bbb",
            },
            {
                "id": "jitsi",
                "name": _("Jitsi Meet"),
                "icon": "fa-video-camera",
                "badge": f"{jitsi_qs.filter(active=True).count()} / {jitsi_qs.count()} " + str(_("servers")),
                "description": _("Lightweight interactive video meeting rooms powered by Jitsi Meet."),
                "enabled": visibility.get("jitsi", {}).get("organizer", True) and visibility.get("jitsi", {}).get("attendee", True),
                "organizer": visibility.get("jitsi", {}).get("organizer", True),
                "attendee": visibility.get("jitsi", {}).get("attendee", True),
                "server_tab": "jitsi",
            },
            {
                "id": "janus",
                "name": _("Janus WebRTC"),
                "icon": "fa-users",
                "badge": f"{janus_qs.filter(active=True).count()} / {janus_qs.count()} " + str(_("servers")),
                "description": _("Low-latency WebRTC video conferencing and room calls powered by Janus."),
                "enabled": visibility.get("janus", {}).get("organizer", True) and visibility.get("janus", {}).get("attendee", True),
                "organizer": visibility.get("janus", {}).get("organizer", True),
                "attendee": visibility.get("janus", {}).get("attendee", True),
                "server_tab": "janus",
            },
            {
                "id": "loungemesh",
                "name": _("LoungeMesh"),
                "icon": "fa-cubes",
                "badge": f"{loungemesh_qs.filter(active=True).count()} / {loungemesh_qs.count()} " + str(_("servers")),
                "description": _("Spatial 2D/3D networking proximity lounge with embedded whiteboards and collaborative notes."),
                "enabled": visibility.get("loungemesh", {}).get("organizer", True) and visibility.get("loungemesh", {}).get("attendee", True),
                "organizer": visibility.get("loungemesh", {}).get("organizer", True),
                "attendee": visibility.get("loungemesh", {}).get("attendee", True),
                "server_tab": "loungemesh",
            },
            {
                "id": "zoom",
                "name": _("Zoom"),
                "icon": "fa-video-camera",
                "badge": str(_("External integration")),
                "description": _("Direct integration for Zoom meetings and webinars embedded into the event space."),
                "enabled": visibility.get("zoom", {}).get("organizer", True) and visibility.get("zoom", {}).get("attendee", True),
                "organizer": visibility.get("zoom", {}).get("organizer", True),
                "attendee": visibility.get("zoom", {}).get("attendee", True),
                "server_tab": None,
            },
        ]
        # Active tab defaults to general
        ctx["active_tab"] = kwargs.get("active_tab") or self.request.GET.get("tab", "general")
        ctx['streaming_selection'] = self.streaming_selection
        event = self.streaming_selection.cleaned_data['event']
        ctx['streaming_event'] = event
        if event:
            with scope(event=event):
                ctx['streaming_page'] = Paginator(
                    StreamSchedule.objects.filter(room__event=event)
                    .select_related('room').order_by('start_time', 'pk'),
                    25,
                ).get_page(self.request.GET.get('stream_page'))
                if 'streaming_form' not in ctx:
                    ctx['streaming_form'] = VideoStreamScheduleForm(
                        event=event, instance=self.streaming_instance,
                    )
        return ctx

    def post(self, request, *args, **kwargs):
        """Save either the selected stream or global provider visibility."""
        if 'stream_action' in request.POST:
            return self.save_streaming(request)
        gs = GlobalSettingsObject()
        changed = []
        for p in SUPPORTED_VIDEO_PROVIDERS:
            sub_key = f"video_provider_{p}_submitted"
            key_single = f"video_provider_{p}"
            org_key = f"video_provider_{p}_organizer"
            att_key = f"video_provider_{p}_attendee"

            # Check if submitted with single unified toggle or role-specific toggles
            if f"{org_key}_submitted" in request.POST or (org_key in request.POST and key_single not in request.POST):
                new_org = request.POST.get(org_key) in ("true", "1", "on")
                new_att = request.POST.get(att_key) in ("true", "1", "on")
                prev_org = gs.settings.get(org_key, as_type=bool, default=True)
                prev_att = gs.settings.get(att_key, as_type=bool, default=True)

                if new_org != prev_org:
                    gs.settings.set(org_key, new_org)
                    changed.append(f"{p} organizer: {new_org}")
                if new_att != prev_att:
                    gs.settings.set(att_key, new_att)
                    changed.append(f"{p} attendee: {new_att}")
            elif sub_key in request.POST or key_single in request.POST:
                is_enabled = request.POST.get(key_single) in ("true", "1", "on")
                for r_key, r_name in [(org_key, "organizer"), (att_key, "attendee")]:
                    prev = gs.settings.get(r_key, as_type=bool, default=True)
                    if is_enabled != prev:
                        gs.settings.set(r_key, is_enabled)
                        changed.append(f"{p} {r_name}: {is_enabled}")

        if changed:
            _admin_log_entry(
                content_object=request.user,
                user=request.user,
                action_type="eventyay.video.settings.visibility_changed",
                data=json.dumps({"changes": changed}),
            )
            messages.success(request, _("Video server visibility settings saved successfully."))
        else:
            messages.info(request, _("No changes made to video server visibility settings."))

        return redirect(reverse("eventyay_admin:video_admin:settings") + "?tab=general")

    def save_streaming(self, request):
        """Save or delete a stream and notify clients after committing its change."""
        event = self.streaming_selection.cleaned_data['event']
        action = request.POST.get('stream_action')
        if not event or action not in ('save', 'delete'):
            raise Http404
        with scope(event=event, organizer=event.organizer):
            instance = self.streaming_instance
            if action == 'delete':
                if not instance:
                    raise Http404
                room, stream_id = instance.room, instance.pk
                with transaction.atomic():
                    instance.delete()
                    event.log_action(
                        'eventyay.stream_schedule.deleted', data={'stream_id': stream_id}, user=request.user, orga=True,
                    )
                    transaction.on_commit(lambda: notify_admin_stream_change(room, event), robust=True)
            else:
                form = VideoStreamScheduleForm(request.POST, event=event, instance=instance)
                if not form.is_valid():
                    return self.render_to_response(self.get_context_data(streaming_form=form, active_tab='streaming'))
                with transaction.atomic():
                    stream = form.save()
                    room = stream.room
                    event.log_action(
                        'eventyay.stream_schedule.saved', data={'stream_id': stream.pk}, user=request.user, orga=True,
                    )
                    transaction.on_commit(lambda: notify_admin_stream_change(room, event), robust=True)
        messages.success(request, _('Streaming configuration saved.'))
        return redirect(reverse('eventyay_admin:video_admin:settings') + f'?tab=streaming&event={event.pk}')


def notify_admin_stream_change(room, event):
    """Refresh the affected room and event after a stream configuration change."""
    async_to_sync(broadcast_stream_change)(room.pk, room.get_current_stream(), reload=True)
    async_to_sync(notify_event_change)(event.pk)


class VideoProviderToggleVisibility(AdministratorPermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"ok": False, "error": _("Invalid JSON payload.")}, status=400)

        if not isinstance(payload, dict):
            return JsonResponse({"ok": False, "error": _("Invalid JSON payload.")}, status=400)

        provider = payload.get("provider")
        role = payload.get("role")
        enabled = payload.get("enabled")

        if provider not in SUPPORTED_VIDEO_PROVIDERS:
            return JsonResponse({"ok": False, "error": _("Unsupported video provider.")}, status=400)

        if not isinstance(enabled, bool):
            return JsonResponse({"ok": False, "error": _("The enabled value must be true or false.")}, status=400)

        gs = GlobalSettingsObject()
        roles_to_update = [role] if role in ("organizer", "attendee") else ["organizer", "attendee"]

        for r in roles_to_update:
            setting_key = f"video_provider_{provider}_{r}"
            gs.settings.set(setting_key, enabled)

        _admin_log_entry(
            content_object=request.user,
            user=request.user,
            action_type=f"eventyay.video.{provider}.visibility_changed",
            data=json.dumps({"provider": provider, "roles": roles_to_update, "enabled": enabled}),
        )

        return JsonResponse({
            "ok": True,
            "provider": provider,
            "enabled": enabled,
            "status": str(_("Enabled")) if enabled else str(_("Disabled")),
        })


class VideoServerToggleActive(AdministratorPermissionRequiredMixin, View):
    def post(self, request, server_type, pk, *args, **kwargs):
        config = get_video_server_config(server_type)
        if not config:
            return JsonResponse(
                {"ok": False, "error": "Unknown video server type."},
                status=404,
            )

        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error": "Invalid JSON payload."},
                status=400,
            )

        active = payload.get("active")
        if not isinstance(active, bool):
            return JsonResponse(
                {"ok": False, "error": "The active value must be true or false."},
                status=400,
            )

        model = config.model
        try:
            server = model.objects.get(pk=pk)
        except model.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Video server not found."}, status=404)

        previous_active = bool(server.active)
        server.active = active
        server.save(update_fields=["active"])

        _admin_log_entry(
            content_object=server,
            user=request.user,
            action_type=f"{config.action_prefix}.active_changed",
            data=json.dumps(
                {
                    "active": active,
                    "previous_active": previous_active,
                }
            ),
        )

        return JsonResponse(
            {
                "ok": True,
                "active": active,
                "status": _("Active") if active else _("Inactive"),
            }
        )


class EventList(AdministratorPermissionRequiredMixin, ListView):
    template_name = "control/event_list.html"
    queryset = (
        Event.objects.annotate(
            user_count=Count("user"),
            last_usage=Subquery(
                PlannedUsage.objects.filter(event=OuterRef("pk"))
                .order_by()
                .values("event")
                .annotate(end=Max("end"))
                .values("end")
            ),
        )
        .prefetch_related("planned_usages")
        .order_by(
            F("last_usage").desc(nulls_last=True),
            F("domain").asc(nulls_last=True),
        )
    )
    context_object_name = "events"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)

        for event in ctx["events"]:
            if event.config and event.config.get("JWT_secrets"):
                event.admin_token = True
        return ctx


class EventAdminToken(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/event_clear.html"
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def get_object(self, queryset=None):
        """
        Override get_object to handle both slug and pk lookups
        """
        if queryset is None:
            queryset = self.get_queryset()

        pk = self.kwargs.get('pk')
        if pk is None:
            raise AttributeError("EventAdminToken view must be called with a pk argument.")

        # Try to get the object by pk first (if it's numeric)
        try:
            if pk.isdigit():
                return queryset.get(pk=pk)
        except Event.DoesNotExist:
            pass

        # If pk lookup fails or pk is not numeric, try slug lookup
        try:
            return queryset.get(slug=pk)
        except Event.DoesNotExist:
            from django.http import Http404
            raise Http404("Event not found")

    def get(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        event = self.get_object()

        # Ensure JWT configuration exists
        if not event.config or not event.config.get("JWT_secrets"):
            from django.utils.crypto import get_random_string
            from django.conf import settings

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

            # Also set up the video plugin settings for the video frontend
            try:
                event.settings.venueless_secret = secret
                event.settings.venueless_issuer = "any"
                event.settings.venueless_audience = "eventyay"
                # Point to SPA at /video/<event_slug>
                base_site = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
                event.settings.venueless_url = f"{base_site}/video/{event.slug}"
            except Exception:
                pass

        _admin_log_entry(
            content_object=event,
            user=self.request.user,
            action_type="event.adminaccess",
            data={},
        )

        return redirect(f"/video/event/{event.organizer.slug}/{event.slug}/")


class FormsetMixin:
    @cached_property
    def formset(self):
        return PlannedUsageFormSet(
            data=self.request.POST if self.request.method == "POST" else None,
            instance=self.object,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["formset"] = self.formset
        return ctx


class EventCreate(FormsetMixin, AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/event_create.html"
    form_class = EventForm
    success_url = "/admin/video/events/"

    @cached_property
    def copy_from(self):
        if self.request.GET.get("copy_from") and not getattr(self, "object", None):
            try:
                return Event.objects.get(pk=self.request.GET.get("copy_from"))
            except Event.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.copy_from:
            inst = copy.copy(self.copy_from)
            inst.pk = None
            inst.domain = None
            # Generate a new unique slug to avoid IntegrityError
            base_slug = self.copy_from.slug
            counter = 1
            new_slug = f"{base_slug}-copy"
            while Event.objects.filter(organizer=self.copy_from.organizer, slug=new_slug).exists():
                new_slug = f"{base_slug}-copy-{counter}"
                counter += 1
            inst.slug = new_slug
            kwargs["instance"] = inst
        return kwargs

    @transaction.atomic()
    def form_valid(self, form):
        secret = get_random_string(length=64)
        form.instance.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
        }
        if self.copy_from:
            form.instance.clone_from(self.copy_from, new_secrets=True)
            form.instance.copy_data_from(self.copy_from)

        self.object = form.save()

        # Initialize Eventyay Video (ticket-video) defaults so the video frontend works immediately
        try:
            secret = form.instance.config["JWT_secrets"][0]["secret"]
            issuer = form.instance.config["JWT_secrets"][0]["issuer"]
            audience = form.instance.config["JWT_secrets"][0]["audience"]
            self.object.settings.venueless_secret = secret
            self.object.settings.venueless_issuer = issuer
            self.object.settings.venueless_audience = audience
            # Point to SPA at /video/<event_id>
            base_site = settings.SITE_URL.rstrip('/')
            self.object.settings.venueless_url = f"{base_site}/video/{self.object.pk}"
            if self.copy_from and self.copy_from.settings.get('event_type') == 'meetup':
                self.object.settings.set('meetup_video_active', True)
        except (KeyError, IndexError, TypeError, AttributeError):
            pass

        for f in self.formset.extra_forms:
            if not f.has_changed():
                continue
            if self.formset._should_delete_form(f):
                continue
            f.instance.event = self.object
            f.save()

        if self.copy_from:
            try:
                secret = form.instance.config["JWT_secrets"][0]["secret"]
                issuer = form.instance.config["JWT_secrets"][0]["issuer"]
                audience = form.instance.config["JWT_secrets"][0]["audience"]
                self.object.settings.venueless_secret = secret
                self.object.settings.venueless_issuer = issuer
                self.object.settings.venueless_audience = audience
                base_site = settings.SITE_URL.rstrip('/')
                self.object.settings.venueless_url = f"{base_site}/video/{self.object.pk}"
            except (KeyError, IndexError, TypeError, AttributeError):
                pass

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="event.created",
            data={
                "copy_from": self.copy_from.pk if self.copy_from else None,
                **form.cleaned_data,
            },
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["copy_from"] = self.copy_from
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class EventUpdate(FormsetMixin, AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/event_update.html"
    form_class = EventForm
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        config = self.object.config or {}
        ctx["jwtconf"] = json.dumps(config.get("JWT_secrets", []), indent=4)
        return ctx

    def form_valid(self, form):
        self.formset.save()
        _admin_log_entry(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="event.updated",
            data=form.cleaned_data,
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class EventClear(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/event_clear.html"
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def post(self, request, *args, **kwargs):
        _admin_log_entry(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="event.cleared",
            data={},
        )
        clear_event_data.apply_async(kwargs={"event": self.get_object().pk})
        messages.success(request, _("The data will soon be deleted."))
        return redirect(self.success_url)





class BBBServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    success_url = "/admin/video/bbbs/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="bbbserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class BBBServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    queryset = BBBServer.objects.all()
    success_url = "/admin/video/bbbs/"

    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="bbbserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class BBBServerDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    template_name = "control/bbb_delete.html"
    queryset = BBBServer.objects.all()
    success_url = "/admin/video/bbbs/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        with transaction.atomic():
            _admin_log_entry(
                content_object=self.object,
                user=self.request.user,
                action_type="bbbserver.deleted",
                data={},
            )
            self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)





class JanusServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    success_url = "/admin/video/janus/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="janusserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JanusServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    queryset = JanusServer.objects.all()
    success_url = "/admin/video/janus/"

    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="janusserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JanusServerDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    template_name = "control/janus_delete.html"
    queryset = JanusServer.objects.all()
    success_url = "/admin/video/janus/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        with transaction.atomic():
            _admin_log_entry(
                content_object=self.object,
                user=self.request.user,
                action_type="janusserver.deleted",
                data={},
            )
            self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)





class JitsiServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/jitsi_form.html"
    form_class = JitsiServerForm
    success_url = "/admin/video/jitsi/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="jitsiserver.created",
            data=_redact_jitsi_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JitsiServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/jitsi_form.html"
    form_class = JitsiServerForm
    queryset = JitsiServer.objects.all()
    success_url = "/admin/video/jitsi/"

    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="jitsiserver.updated",
            data=_redact_jitsi_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JitsiServerDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    template_name = "control/jitsi_delete.html"
    queryset = JitsiServer.objects.all()
    success_url = "/admin/video/jitsi/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        with transaction.atomic():
            _admin_log_entry(
                content_object=self.object,
                user=self.request.user,
                action_type="jitsiserver.deleted",
                data={},
            )
            self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


def _redact_jitsi_server_log_data(data):
    return {
        key: "*****" if key == "app_secret" and value else str(value)
        for key, value in data.items()
    }





class TurnServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    success_url = "/admin/video/turns/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="turnserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class TurnServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    queryset = TurnServer.objects.all()
    success_url = "/admin/video/turns/"

    def form_valid(self, form):
        self.object = form.save()

        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="turnserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class TurnServerDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    template_name = "control/turn_delete.html"
    queryset = TurnServer.objects.all()
    success_url = "/admin/video/turns/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        with transaction.atomic():
            _admin_log_entry(
                content_object=self.object,
                user=self.request.user,
                action_type="turnserver.deleted",
                data={},
            )
            self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


def _redact_loungemesh_server_log_data(data):
    return {
        key: "*****" if key in ("api_secret", "jitsi_app_secret") and value else str(value)
        for key, value in data.items()
    }


class LoungeMeshServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/loungemesh_form.html"
    form_class = LoungeMeshServerForm
    success_url = "/admin/video/loungemesh/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()
        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="loungemeshserver.created",
            data=_redact_loungemesh_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class LoungeMeshServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/loungemesh_form.html"
    form_class = LoungeMeshServerForm
    queryset = LoungeMeshServer.objects.all()
    success_url = "/admin/video/loungemesh/"

    def form_valid(self, form):
        self.object = form.save()
        _admin_log_entry(
            content_object=form.instance,
            user=self.request.user,
            action_type="loungemeshserver.updated",
            data=_redact_loungemesh_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class LoungeMeshServerDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    template_name = "control/loungemesh_delete.html"
    queryset = LoungeMeshServer.objects.all()
    success_url = "/admin/video/loungemesh/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        with transaction.atomic():
            _admin_log_entry(
                content_object=self.object,
                user=self.request.user,
                action_type="loungemeshserver.deleted",
                data={},
            )
            self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


class SystemLogList(AdministratorPermissionRequiredMixin, ListView):
    template_name = "control/systemlog_list.html"
    queryset = SystemLog.objects.order_by("-timestamp")
    context_object_name = "systemlogs"
    paginate_by = 25


class SystemLogDetail(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/systemlog_detail.html"
    queryset = SystemLog.objects.all()
    context_object_name = "systemlog"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trace"] = json.loads(self.object.trace)
        return ctx


class EventCalendar(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = PlannedUsage.objects.all().select_related("event")
        calendar = icalendar.Calendar()
        for planned_usage in queryset:
            calendar.add_component(planned_usage.as_ical())

        return HttpResponse(
            calendar.to_ical(),
            content_type="text/calendar",
            headers={"Content-Disposition": 'attachment; filename="eventyay.ics"'},
        )





class BBBMoveRoom(AdministratorPermissionRequiredMixin, FormView):
    template_name = "control/bbb_moveroom.html"
    form_class = BBBMoveRoomForm

    def form_valid(self, form):
        server = form.cleaned_data["server"]
        room = form.cleaned_data["room"]

        try:
            c = BBBCall.objects.get(room=room)
        except BBBCall.DoesNotExist:
            messages.error(self.request, _("No BBB session found for this room."))
            return HttpResponseRedirect(self.request.path)
        source_server = c.server
        try:
            u = get_url(
                "end",
                {"meetingID": c.meeting_id, "password": c.moderator_pw},
                source_server.url,
                source_server.secret,
            )
            r = requests.get(u, timeout=15)
            r.raise_for_status()
            log_event(
                'video',
                'recording.stop',
                OUTCOME_SUCCESS,
                event_id=getattr(room, 'event_id', None),
                object_id=getattr(room, 'pk', None),
                backend='bbb',
            )
        except Exception:
            log_event('video', 'connection.get', OUTCOME_FAILURE, error_code='request_error', backend='bbb')
            messages.warning(self.request, _("Kicking all attendees did not work."))

        c.server = server
        c.save()
        messages.success(self.request, _("Moved."))
        return HttpResponseRedirect(self.request.path)
