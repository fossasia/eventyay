import logging

from django.contrib.auth import user_logged_out
from django.dispatch import receiver

from django_sso.sso_service import request_deauthentication


@receiver(user_logged_out)
def push_deauthenticate_user_event(user, *args, **kwargs):
    try:
        request_deauthentication(user)
    except Exception as e:
        logging.critical(f"SSO deauthentication event send failed to gateway: {e}")