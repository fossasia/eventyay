from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.module_loading import import_string
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from random import randint
import logging

from ..common import write_session, login, disabled_fallbacks
from ..app_settings import mf_settings


logger = logging.getLogger(__name__)

SESSION_KEY = 'multifactor-fallback-otp'
SESSION_KEY_SUCCEEDED = 'multifactor-fallback-succeeded'


class Auth(LoginRequiredMixin, TemplateView):
    template_name = "multifactor/fallback/auth.html"

    def get(self, request, generate=True):
        if generate:
            otp = request.session[SESSION_KEY] = request.session.get(SESSION_KEY, str(randint(0, 100000000)))
            message = f'Your one-time-password is: {otp}'
            if request.user.get_full_name():
                message = f'Dear {request.user.get_full_name()},\n{message}'

            disabled = disabled_fallbacks(request)
            s = []
            for name, (field, method) in mf_settings['FALLBACKS'].items():
                if name in disabled or not field(request.user):
                    continue

                try:
                    imported_method = import_string(method)
                    if imported_method(request.user, message):
                        s.append(name)
                except:
                    pass

            if not s:
                messages.error(request, 'No fallback one-time-password transport methods worked. Please contact an administrator.')
                return redirect('multifactor:home')

            request.session[SESSION_KEY_SUCCEEDED] = s[0] if len(s) == 1 else (', '.join(s[:-1]) + ' and ' + s[-1])

        return super().get(
            request,
            succeeded=request.session[SESSION_KEY_SUCCEEDED],
        )

    def post(self, request):
        if request.session[SESSION_KEY] == request.POST["otp"].strip():
            request.session.pop(SESSION_KEY)
            write_session(request, key=None)
            return login(request)

        messages.error(request, 'That key was not correct. Please try again.')
        return self.get(request, generate=False)


def send_email(user, message):
    try:
        msg = EmailMultiAlternatives(
            subject='One Time Password',
            body=message,
            from_email=settings.SERVER_EMAIL,
            to=[user.email]
        )

        if mf_settings['HTML_EMAIL']:
            # add a HTML version if allowed
            html_message = render_to_string(
                'multifactor/fallback/email.html',
                {'user': user, 'message': message}
            )
            msg.attach_alternative(html_message, "text/html")

        msg.send()

        return "email"
    except Exception:
        logger.exception('Could not send email:', user)
        return False


def debug_print_console(user, message):
    print(user, message)
    return "command line"
