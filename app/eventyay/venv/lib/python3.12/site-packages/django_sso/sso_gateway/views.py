import json
import logging
from builtins import super
from typing import Optional

import django.contrib.auth.views
from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.base import View
from django.views.generic.edit import FormView

from .models import Service, AuthenticationRequest
from .. import deauthenticate_user
from ..exceptions import SSOException


class LoginView(django.contrib.auth.views.LoginView):
	template_name = 'django_sso/login.html'

	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		if not request.user.is_anonymous:
			return redirect(self.get_success_url())

		return super(FormView, self).dispatch(request, *args, **kwargs)

	def get_success_url(self):
		sso_request_token = self.request.GET.get('sso', '').strip()
		auth_request = None

		if sso_request_token:
			auth_request: Optional[AuthenticationRequest] = AuthenticationRequest.objects.filter(
				token=sso_request_token,
				used=False,
			).first()

		LOGIN_REDIRECT_URL = getattr(settings, 'LOGIN_REDIRECT_URL', reverse_lazy('welcome'))

		if not auth_request or not auth_request.next_url:
			return LOGIN_REDIRECT_URL

		try:
			auth_request.activate(self.request.user)
		except SSOException as e:
			logging.critical(f'Failed to emit login event to subordinated service {auth_request.service}: {e}')

			return LOGIN_REDIRECT_URL + '?fallback=true'

		return f'{auth_request.service.base_url}/sso/accept/'

	def form_valid(self, form):
		super().form_valid(form)

		return redirect(self.get_success_url())


class LogoutView(View):
	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def get(self, request):
		logout(request)

		return redirect(reverse_lazy('login'))


class ObtainView(View):
	"""
	The view for Subordinated services for obtain SSO token
	"""

	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def post(self, request):
		if not request.POST.get('token', '').strip():
			return JsonResponse({"error": _('"token" isn\'t set')})

		if not request.POST.get('next_url', '').strip():
			return JsonResponse({"error": _('"next_url" isn\'t set')})

		service = Service.objects.filter(enabled=True, token=request.POST['token']).first()

		if not service:
			return JsonResponse({"error": _("Application token doesn't exist")})

		sso_request = AuthenticationRequest(
			service=service,
			next_url=request.POST['next_url']
		)

		sso_request.save()

		return JsonResponse({'token': sso_request.token})


class GetAuthenticationRequestView(View):
	"""
	The view for the services to do obtain information about the authentication request by SSO-token
	If
	- token exist for requested sso_service
	- token are activated and wasn't used yet for login
	will be returned the authentication request information as is, else 401 code with error
	"""

	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def post(self, request):
		if not request.POST.get('token', '').strip():
			return JsonResponse({"error": _('"token" isn\'t set')})

		service = Service.objects.filter(enabled=True, token=request.POST['token']).first()

		if not service:
			return JsonResponse({"error": _("Application token doesn't exist")})

		if not request.POST.get('authentication_token', '').strip():
			return JsonResponse({"error": _("Authentication request token doesn't set")})

		authorization_request = AuthenticationRequest.objects.filter(
			token=request.POST.get('authentication_token'),
			service=service,
			authenticated=True,
			used=False,
		).first()

		if not authorization_request:
			return JsonResponse({"error": _("Authentication request token doesn't exist")})
		else:
			return JsonResponse({
				"authenticated": True,
				"user_identy": authorization_request.user_identy,
				"next_url": authorization_request.next_url
			})


class MakeUsedView(View):
	"""
	The view who mark authentication request as used
	"""

	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def post(self, request):
		if not request.POST.get('token', '').strip():
			return JsonResponse({"error": _('"token" isn\'t set')})

		service = Service.objects.filter(enabled=True, token=request.POST['token']).first()

		if not service:
			return JsonResponse({"error": _("Application token doesn't exist")})

		if not request.POST.get('authentication_token', '').strip():
			return JsonResponse({"error": _("Authentication request token doesn't set")})

		authorization_request = AuthenticationRequest.objects.filter(
			token=request.POST.get('authentication_token'),
			service=service,
			authenticated=True,
			used=False,
		).first()

		if not authorization_request:
			return JsonResponse({"error": _("Authentication request token doesn't exist")}, status=404)
		else:
			authorization_request.authenticated = True
			authorization_request.save()

			return JsonResponse({"ok": True})


class DeauthenticateView(View):
	"""
	Deauthenticate user everywhere by identy.
	Deauth on all services except requester
	"""

	@csrf_exempt
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)

	def post(self, request):
		if not request.POST.get('token', '').strip():
			return JsonResponse({"error": _('"token" isn\'t set')})

		if not request.POST.get('user_identy', '').strip():
			return JsonResponse({"error": _('"user_identy" isn\'t set')})

		service = Service.objects.filter(enabled=True, token=request.POST['token']).first()

		user_model = get_user_model()

		user = user_model.objects.filter(**{
			f'{user_model.USERNAME_FIELD}': request.POST['user_identy']
		}).first()

		if user:
			deauthenticate_user(getattr(user, user_model.USERNAME_FIELD))

			for instance in Service.objects.filter(enabled=True).exclude(id=service.id).all():
				instance.deauthenticate(user)

		return JsonResponse({'ok': True})


class DebugUpdateEvent(TemplateView):
	template_name = 'django_sso/debug_update_event.html'

	def get_context_data(self, **kwargs):
		kwargs.update({
			'event': json.dumps(Service.build_update_user_event(self.request.user), indent=3)
		})

		return kwargs
