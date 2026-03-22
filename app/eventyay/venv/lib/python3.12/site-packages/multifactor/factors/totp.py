from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

import pyotp

from ..models import UserKey, KeyTypes
from ..common import write_session, login
from ..app_settings import mf_settings
from ..mixins import PreferMultiAuthMixin


WINDOW = 60


class Create(PreferMultiAuthMixin, TemplateView):
    template_name = "multifactor/TOTP/add.html"

    def dispatch(self, request, *args, **kwargs):
        self.secret_key = request.POST.get("key", pyotp.random_base32())
        self.totp = pyotp.TOTP(self.secret_key)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "qr": self.totp.provisioning_uri(
                self.request.user.get_username(),
                issuer_name=mf_settings['TOKEN_ISSUER_NAME']
            ),
            "secret_key": self.secret_key,
        }

    def post(self, request, *args, **kwargs):
        if self.totp.verify(request.POST["answer"], valid_window=WINDOW):
            key = UserKey.objects.create(
                user=request.user,
                properties={"secret_key": self.secret_key},
                key_type=str(KeyTypes.TOTP)
            )
            write_session(request, key)
            messages.success(request, 'TOTP Authenticator added.')
            return redirect("multifactor:home")

        messages.error(request, 'Could not validate key, please try again.')
        return super().get(request, *args, **kwargs)


class Auth(LoginRequiredMixin, TemplateView):
    template_name = "multifactor/TOTP/check.html"

    def post(self, request, *args, **kwargs):
        key = self.verify_login(token=request.POST["answer"])
        if key:
            write_session(request, key)
            return login(request)

        messages.error(request, 'Could not validate key, please try again.')
        return super().get(request, *args, **kwargs)

    def verify_login(self, token):
        for key in UserKey.objects.filter(user=self.request.user, key_type=str(KeyTypes.TOTP), enabled=True):
            if pyotp.TOTP(key.properties["secret_key"]).verify(token, valid_window=WINDOW):
                return key
