import datetime as dt
from http import HTTPMethod

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views.generic import FormView

from eventyay.base.auth import get_auth_backends
from eventyay.base.models import User
from eventyay.cfp.forms.auth import RecoverForm, ResetForm
from eventyay.common.text.phrases import phrases
from eventyay.common.views import GenericLoginView, GenericResetView


class LoginView(GenericLoginView):
    template_name = 'orga/auth/login.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        backenddict = get_auth_backends()
        backend = backenddict.get(self.request.GET.get('backend', 'native'), None)
        if not backend and backenddict:
            backend = list(backenddict.values())[0]

        backend.url = backend.authentication_url(self.request)
        kwargs['backend'] = backend
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = settings.INSTANCE_NAME
        return context

    @cached_property
    def event(self):
        return getattr(self.request, 'event', None)

    @cached_property
    def success_url(self):
        if self.event:
            return self.event.orga_urls.base
        return reverse('orga:event.list')

    def get_password_reset_link(self):
        if self.event:
            return reverse('orga:event.auth.reset', kwargs={'event': self.event.slug})
        return reverse('orga:auth.reset')


def logout_view(request):
    if request.method == HTTPMethod.POST:
        logout(request)
    response = redirect(GenericLoginView.get_next_url_or_fallback(request, reverse('orga:login')))
    if request.method == HTTPMethod.POST:
        # Remove the JWT cookie
        response.delete_cookie('sso_token')  # Same domain used when setting the cookie
        response.delete_cookie('customer_sso_token')
    return response


class ResetView(GenericResetView):
    template_name = 'orga/auth/reset.html'
    form_class = ResetForm

    def get_success_url(self):
        if getattr(self.request, 'event', None):
            return reverse('orga:event.login', kwargs={'event': self.request.event.slug})
        return reverse('orga:login')


class RecoverView(FormView):
    template_name = 'orga/auth/recover.html'
    form_class = RecoverForm

    def __init__(self, **kwargs):
        self.user = None
        super().__init__(**kwargs)

    def get_user(self):
        return User.objects.get(
            pw_reset_token=self.kwargs.get('token'),
            pw_reset_time__gte=now() - dt.timedelta(days=1),
        )

    def dispatch(self, request, *args, **kwargs):
        try:
            self.get_user()
        except User.DoesNotExist:
            messages.error(self.request, phrases.cfp.auth_reset_fail)
            return redirect(reverse('orga:auth.reset'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.get_user()
        user.change_password(form.cleaned_data['password'])
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('orga:login')
