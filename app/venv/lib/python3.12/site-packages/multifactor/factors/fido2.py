from importlib.metadata import version
from packaging.version import Version

from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View

from fido2.server import Fido2Server
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialUserEntity
from fido2.utils import websafe_decode, websafe_encode
import fido2.features
import logging

from ..models import UserKey, KeyTypes
from ..common import write_session, login
from ..app_settings import mf_settings
from ..mixins import PreferMultiAuthMixin

import json

if Version(version("fido2")) < Version("2.0.0"): # 2.0.0+ no longer requies this
    fido2.features.webauthn_json_mapping.enabled = True

logger = logging.getLogger(__name__)

class FidoClass(View):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return csrf_exempt(view)

    @property
    def server(self):
        return Fido2Server(rp=dict(
            id=mf_settings['FIDO_SERVER_ID'],
            name=mf_settings['FIDO_SERVER_NAME']
        ))

    def get_user_credentials(self):
        if not self.request.user.is_authenticated:
            return []
        return [
            AttestedCredentialData(websafe_decode(key.properties["device"]))
            for key in UserKey.objects.filter(
                user=self.request.user,
                key_type=str(KeyTypes.FIDO2),
                properties__domain=self.request.get_host().split(":")[0],
                enabled=True,
            )
        ]


class Register(PreferMultiAuthMixin, FidoClass):
    def get(self, request, *args, **kwargs):
        registration_data, state = self.server.register_begin(
            user=PublicKeyCredentialUserEntity(
                id=request.user.get_username().encode('utf-8'),
                name=f'{request.user.get_full_name()}',
                display_name=request.user.get_username(),
            ),
            credentials=self.get_user_credentials(),
        )
        request.session['fido_state'] = state

        return JsonResponse({**registration_data}, safe=False)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            auth_data = self.server.register_complete(
                request.session['fido_state'], data)

            encoded = websafe_encode(auth_data.credential_data)
            key = UserKey.objects.create(
                user=request.user,
                properties={
                    "device": encoded,
                    "type": data['type'],
                    "domain": self.server.rp.id,
                },
                key_type=str(KeyTypes.FIDO2),
            )
            write_session(request, key)
            messages.success(request, 'FIDO2 Token added!')
            return JsonResponse({'status': 'OK'})

        except:
            logger.exception("Error completing FIDO2 registration.")
            return JsonResponse({
                'status': 'ERR',
                "message": "Error on server, please try again later",
            })


class Authenticate(LoginRequiredMixin, FidoClass):
    def get(self, request, *args, **kwargs):
        auth_data, state = self.server.authenticate_begin(
            credentials=self.get_user_credentials(),
            user_verification="discouraged",
        )
        request.session['fido_state'] = state
        return JsonResponse({**auth_data})

    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)

        cred = self.server.authenticate_complete(
            request.session.pop('fido_state'),
            self.get_user_credentials(),
            data
        )

        keys = UserKey.objects.filter(
            user=request.user,
            key_type=str(KeyTypes.FIDO2),
            enabled=True,
        )

        for key in keys:
            if AttestedCredentialData(websafe_decode(key.properties["device"])).credential_id == cred.credential_id:
                write_session(request, key)
                res = login(request)
                return JsonResponse({'status': "OK", "redirect": res["location"]})

        return JsonResponse({'status': "err"})
