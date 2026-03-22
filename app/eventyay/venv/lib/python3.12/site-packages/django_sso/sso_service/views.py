import importlib
import urllib.parse
import json

from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
import django.contrib.auth

from django_sso.exceptions import SSOException
from django_sso.sso_gateway import set_sso_authorization_request_used
from django_sso.sso_service import get_sso_authorization_request, request_sso_authorization_request, \
    request_deauthentication


def login_view(request):
    """
    The view to redirect to SSO for authentication
    """
    try:
        sso_token = request_sso_authorization_request(request)
        request.session['token'] = sso_token
    except SSOException as e:
        return render(
            request,
            template_name='django_sso/token_validation_error.html',
            context={
                'error': str(e),
                'debug': settings.DEBUG
            }
        )

    params = urllib.parse.urlencode({'sso': sso_token})

    return render(
        request,
        context={
            'redirect_url': f"{settings.SSO['ROOT']}/login/?{params}"
        },
        template_name='django_sso/redirect_to_sso.html'
    )


@login_required
def for_logged_only_view(request):
    """
    The view for testing mechanism
    """
    user_model = get_user_model()
    return HttpResponse(f'{_("You authorized as")} <b>{getattr(request.user, user_model.USERNAME_FIELD)}</b>.')


def authorize_from_sso_view(request: WSGIRequest):
    """
    Авторизует пользователя, который вернулся от SSO-сервера
    """
    if not request.session.session_key or not request.session.get('token', ''):
        return redirect('/')

    try:
        authorization_request = get_sso_authorization_request(request.session.get('token'))

        user_model = get_user_model()

        user = user_model.objects.filter(
            **{f'{user_model.USERNAME_FIELD}': authorization_request['user_identy']}
        ).first()

        if not user:
            raise SSOException(_('Local user for SSO does not exist'))

        set_sso_authorization_request_used(request.session.get('token'))

        login(request, user)

        if authorization_request['next_url']:
            return redirect(authorization_request['next_url'])
        else:
            return redirect('/')
    except SSOException as e:
        if settings.DEBUG:
            return render(request, 'django_sso/token_validation_error.html', context={
                'error': e
            })
        else:
            return redirect('/?sso_broken_token=true')


def logout(request):
    if not request.user.is_anonymous:
        try:
            django.contrib.auth.logout(request)
        except Exception as e:
            if settings.DEBUG:
                return render(request, template_name='django_sso/deauthentication_error.html', context={
                    'error': e
                })

    return redirect('/')


@csrf_exempt
def event_acceptor_view(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode('utf8'))
    except:
        return HttpResponse(status=400)

    if (
            not data.get('token', '').strip()
            or data.pop('token') != settings.SSO['TOKEN']
    ):
        return JsonResponse({
            'error': _('Token not provided or incorrect')
        })

    if not data.get('type', '').strip():
        return JsonResponse({'error': _('Event type field not set')})

    try:
        type_name = str(data.pop('type')).strip()

        if type_name.startswith('_'):
            return JsonResponse({'error': _('Incorrect event type name')})

        module_name, class_name = settings.SSO.get(
            'EVENT_ACCEPTOR_CLASS',
            'django_sso.sso_service.backend.EventAcceptor'
        ).rsplit('.', 1)

        dispatcher_class = getattr(importlib.import_module(module_name), class_name)

        if (
            hasattr(dispatcher_class, type_name)
            and hasattr(getattr(dispatcher_class, type_name), '__is_sso_event_acceptor')
            and getattr(dispatcher_class, type_name).__is_sso_event_acceptor
        ):
            try:
                getattr(dispatcher_class(), type_name)(**data)
            except Exception as e:
                return JsonResponse({'error': str(e)})

            return JsonResponse({'ok': True})
        else:
            return JsonResponse({'error': f"{_('Event type not supported')} ({type_name})"})

    except Exception as e:
        return JsonResponse({'error': str(e)})
