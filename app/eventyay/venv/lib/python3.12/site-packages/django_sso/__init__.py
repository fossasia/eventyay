from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model


def deauthenticate_user(user_identy):
    """
    Deauthenticates user in currently runing context
    """
    from django.contrib.sessions.models import Session

    user_model = get_user_model()

    user = user_model.objects.filter(**{
        f'{user_model.USERNAME_FIELD}': user_identy
    }).first()

    if user:
        for session_key in Session.objects.values_list('session_key', flat=True).all():
            session = import_module(settings.SESSION_ENGINE).SessionStore(session_key)

            if '_auth_user_id' in session and int(session['_auth_user_id']) == user.id:
                del session['_auth_user_id']

                if '_auth_user_backend' in session:
                    del session['_auth_user_backend']

                if '_auth_user_hash' in session:
                    del session['_auth_user_hash']

                session.save()







