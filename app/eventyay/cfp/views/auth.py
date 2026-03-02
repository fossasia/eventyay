import datetime as dt
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, login as django_login
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, View
from django_context_decorator import context

from eventyay.cfp.forms.auth import RecoverForm
from eventyay.cfp.views.event import EventPageMixin
from eventyay.common.text.phrases import phrases
from eventyay.common.views import GenericLoginView, GenericResetView
from eventyay.base.models import User
from eventyay.base.forms.auth import LoginForm
from eventyay.base.auth import get_auth_backends

SessionStore = import_string(f'{settings.SESSION_ENGINE}.SessionStore')
logger = logging.getLogger(__name__)


class LogoutView(View):
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        logout(request)
        response = self.get(request, *args, **kwargs)
        # Remove the JWT cookie
        response.delete_cookie('sso_token')  # Same domain used when setting the cookie
        response.delete_cookie('customer_sso_token')
        return response

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        return redirect(reverse('cfp:event.start', kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug}))


class LoginView(GenericLoginView):
    template_name = 'cfp/event/login.html'
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        if not request.event.is_public:
            logger.info('Event %s is not public. Blocking access.', request.event.slug)
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_error_url(self):
        return self.request.event.urls.base

    @property
    def success_url(self):
        return self.request.event.urls.user_submissions

    def get_password_reset_link(self):
        return self.request.event.urls.reset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        backenddict = get_auth_backends()
        backend = backenddict.get('native') or list(backenddict.values())[0]
        # Populate backend.url as LoginForm expects it in __init__
        try:
            backend.url = backend.authentication_url(self.request)
        except AttributeError:
            backend.url = None
        kwargs.update({'backend': backend, 'request': self.request})
        return kwargs

    def form_valid(self, form):
        user = form.get_user()
        if not user:
            return self.form_invalid(form)
        django_login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return self.get_redirect()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # We already have a primary login button in this page, disable the subheader login link.
        context['subheader_login_link_disabled'] = True
        return context


class ResetView(EventPageMixin, GenericResetView):
    template_name = 'cfp/event/reset.html'

    def get_success_url(self):
        return reverse('cfp:event.login', kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug})


class RecoverView(FormView):
    template_name = 'cfp/event/recover.html'
    form_class = RecoverForm
    is_invite = False

    def __init__(self, **kwargs):
        self.user = None
        super().__init__(**kwargs)

    @context
    def is_invite_template(self):
        return self.is_invite

    def dispatch(self, request, *args, **kwargs):
        try:
            self.user = User.objects.get(
                pw_reset_token=kwargs.get('token'),
                pw_reset_time__gte=now() - dt.timedelta(days=1),
            )
        except User.DoesNotExist:
            messages.error(self.request, phrases.cfp.auth_reset_fail)
            return redirect(reverse('cfp:event.reset', kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug}))

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.user.change_password(form.cleaned_data['password'])
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return redirect(reverse('cfp:event.login', kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug}))


class EventAuth(View):
    """Taken from pretix' brilliant solution for multidomain auth."""

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def post(request, *args, **kwargs):
        store = SessionStore(request.POST.get('session'))

        try:
            data = store.load()
        except Exception:
            raise PermissionDenied(phrases.base.back_try_again)

        key = f'eventyay_event_access_{request.event.pk}'
        parent = data.get(key)
        sparent = SessionStore(parent)

        try:
            parentdata = sparent.load()
        except Exception:
            raise PermissionDenied(phrases.base.back_try_again)
        else:
            if 'event_access' not in parentdata:
                raise PermissionDenied(phrases.base.back_try_again)

        request.session[key] = parent
        url = request.event.urls.base
        if target := request.POST.get('target'):
            if target == 'cfp':
                url = request.event.cfp.urls.public
            elif target == 'schedule':
                url = request.event.urls.schedule
        return redirect(url)
