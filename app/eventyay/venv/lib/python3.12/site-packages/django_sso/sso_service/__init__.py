import importlib

from django.conf import settings
import requests
from django.contrib.auth import get_user_model

from django_sso.exceptions import SSOException


def request_sso_authorization_request(request) -> str:
    """
    Запрашивает токен авторизации на SSO-шлюзе и возвращает его как результат.
    Необходим для дальнейшей авторизации пользователя на шлюзе авторизации
    """
    try:
        result = requests.post(settings.SSO['ROOT'] + '/sso/obtain/', {
            "token": settings.SSO['TOKEN'],
            "next_url": request.GET.get('next', '/'),
        })

        if result.status_code != 200:
            raise Exception(f'Некорректный ответ сервера авторизации: STATUS={result.status_code}; TEXT={result.text}')

        result = result.json()
    except Exception as e:
        raise SSOException(e)

    if 'token' in result:
        return result['token']
    else:
        raise SSOException(result['error'])


def get_sso_authorization_request(sso_token: str) -> dict:
    """
    Get SSO token information from server to check authorization
    """
    try:
        result = requests.post(settings.SSO['ROOT'] + '/sso/get/', {
            'token': settings.SSO['TOKEN'],
            'authentication_token': sso_token
        })

        if result.status_code != 200:
            raise SSOException(f'Некорректный ответ сервера авторизации: STATUS={result.status_code}; TEXT={result.text}')

        result = result.json()

        if 'error' in result:
            raise SSOException(result['error'])
    except Exception as e:
        raise SSOException(e)

    return result


def request_deauthentication(user):
    """
    Call SSO sso_gateway to deauthorize user everywhere
    """
    user_model = get_user_model()

    try:
        result = requests.post(settings.SSO['ROOT'] + '/sso/deauthenticate/', {
            'token': settings.SSO['TOKEN'],
            'user_identy': getattr(user, user_model.USERNAME_FIELD)
        })

        if result.status_code != 200:
            raise SSOException(
                f'Некорректный ответ сервера авторизации: STATUS={result.status_code}; TEXT={result.text}'
            )

        result = result.json()

        if 'error' in result:
            raise SSOException(result['error'])
    except Exception as e:
        raise SSOException(e)
