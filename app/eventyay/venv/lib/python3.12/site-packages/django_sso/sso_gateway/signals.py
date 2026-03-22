import logging

from django.contrib.auth import user_logged_out, user_logged_in
from django.dispatch import receiver

from .models import Service


@receiver(user_logged_in)
def push_update_user_event(user=None, *args, **kwargs):
    if user:
        for service in Service.objects.filter(enabled=True):
            try:
                service.update_account(user)
            except Exception as e:
                logging.critical(f"Django SSO event dispatching error: {e}")


@receiver(user_logged_out)
def push_deauthenticate_user_event(user=None, *args, **kwargs):
    if user:
        for service in Service.objects.filter(enabled=True):
            try:
                service.deauthenticate(user)
            except Exception as e:
                logging.critical(f"Django SSO event dispatching error: {e}")
