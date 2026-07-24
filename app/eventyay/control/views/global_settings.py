import logging
import secrets
import smtplib


from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, FormView, TemplateView
from python_http_client.exceptions import HTTPError

from eventyay.api.models import OAuthApplication
from eventyay.base.email import CustomSMTPBackend, SendGridEmail
from eventyay.base.models import LogEntry, OrderPayment, OrderRefund
from eventyay.base.services.mail import get_mail_backend
from eventyay.base.services.update_check import check_result_table, update_check
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.global_settings import (
    GlobalSettingsForm,
    SSOConfigForm,
    UpdateSettingsForm,
    StartPageSettingsForm,
)
from eventyay.control.permissions import (
    AdministratorPermissionRequiredMixin,
    StaffMemberRequiredMixin,
)

logger = logging.getLogger(__name__)


class GlobalSettingsView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_settings.html'
    form_class = GlobalSettingsForm

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['test_email_feedback'] = self.request.session.pop('admin_test_email_feedback', None)
        return ctx

    def get_success_url(self):
        return reverse('eventyay_admin:admin.global.settings')


class StartPageSettingsView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/admin/startpage.html'
    form_class = StartPageSettingsForm

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('eventyay_admin:admin.startpage')


class SSOView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_sso.html'
    form_class = SSOConfigForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        oauth_applications = OAuthApplication.objects.all()
        context['oauth_applications'] = oauth_applications
        return context

    def form_valid(self, form):
        url = form.cleaned_data['redirect_url']

        try:
            result = self.create_oauth_application(url)
        except (IntegrityError, ValidationError, ObjectDoesNotExist) as e:
            error_type = type(e).__name__
            logger.error('Error while creating OAuth2 application: %s - %s', error_type, e)
            return self.render_to_response({'error_message': f'{error_type}: {e}'})

        return self.render_to_response(self.get_context_data(form=form, result=result))

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('eventyay_admin:admin.global.sso')

    def create_oauth_application(self, redirect_uris):
        application, created = OAuthApplication.objects.get_or_create(
            redirect_uris=redirect_uris,
            defaults={
                'name': 'Talk SSO Client',
                'client_type': OAuthApplication.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': OAuthApplication.GRANT_AUTHORIZATION_CODE,
                'user': None,
                'client_id': secrets.token_urlsafe(32),
                'client_secret': secrets.token_urlsafe(64),
                'hash_client_secret': False,
                'skip_authorization': True,
            },
        )

        return {
            'success_message': (
                'Successfully created OAuth2 Application'
                if created
                else 'OAuth2 Application with this redirect URI already exists'
            ),
            'client_id': application.client_id,
            'client_secret': application.client_secret,
        }


class DeleteOAuthApplicationView(AdministratorPermissionRequiredMixin, DeleteView):
    model = OAuthApplication
    success_url = reverse_lazy('eventyay_admin:admin.global.sso')


class UpdateCheckView(StaffMemberRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_update.html'
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if 'trigger' in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['gs'] = GlobalSettingsObject()
        ctx['gs'].settings.set('update_check_ack', True)
        ctx['tbl'] = check_result_table()
        return ctx

    def get_success_url(self):
        return reverse('eventyay_admin:admin.global.update')


class MessageView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/global_message.html'


class GlobalSettingsTestEmailView(AdministratorPermissionRequiredMixin, View):
    """
    Tests the current system-level email configuration without saving settings.
    """

    EMAIL_TAB_HASH = '#tab3'

    def _respond(self, request, level, message):
        """Redirect back to the email tab with inline feedback. Does not save settings."""
        request.session['admin_test_email_feedback'] = {
            'level': level,
            'message': str(message),
        }
        return redirect(reverse('eventyay_admin:admin.global.settings') + self.EMAIL_TAB_HASH)

    def post(self, request, *args, **kwargs):
        recipients_raw = request.POST.get('test_email', '').strip()
        recipients = [r.strip() for r in recipients_raw.split(',') if r.strip()]

        if not recipients:
            return self._respond(
                request,
                'error',
                _('Please enter at least one valid recipient email address.'),
            )

        for recipient in recipients:
            try:
                validate_email(recipient)
            except ValidationError:
                return self._respond(
                    request,
                    'error',
                    _('Please enter a valid recipient email address ("%(email)s" is invalid).')
                    % {'email': recipient},
                )

        gs = GlobalSettingsObject()
        raw_from = gs.settings.get('mail_from') or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        mail_from = str(raw_from).strip() if raw_from else ''

        if not mail_from:
            return self._respond(
                request,
                'error',
                _(
                    'No sender address is configured. '
                    'Please set the "Sender address" field in the Email tab and save first.'
                ),
            )

        try:
            validate_email(mail_from)
        except ValidationError:
            return self._respond(
                request,
                'error',
                _(
                    'The sender address "%(addr)s" is not a valid email address. '
                    'Please correct the "Sender address" field and save again.'
                )
                % {'addr': mail_from},
            )

        try:
            mail_from.encode('ascii')
        except UnicodeEncodeError:
            return self._respond(
                request,
                'error',
                _(
                    'The sender address "%(addr)s" contains non-ASCII characters '
                    'which are not allowed in SMTP. '
                    'Please correct the "Sender address" field and save again.'
                )
                % {'addr': mail_from},
            )

        try:
            if gs.settings.email_vendor == 'sendgrid':
                if not gs.settings.send_grid_api_key:
                    return self._respond(
                        request,
                        'error',
                        _('SendGrid API key is missing. Please configure it and save.'),
                    )
                backend = SendGridEmail(api_key=gs.settings.send_grid_api_key)
            elif gs.settings.email_vendor == 'smtp':
                if not gs.settings.smtp_host or not gs.settings.smtp_port:
                    return self._respond(
                        request,
                        'error',
                        _('SMTP host or port is missing. Please configure them and save.'),
                    )
                backend = CustomSMTPBackend(
                    host=gs.settings.smtp_host,
                    port=gs.settings.smtp_port,
                    username=gs.settings.smtp_username,
                    password=gs.settings.smtp_password,
                    use_tls=gs.settings.smtp_use_tls,
                    use_ssl=gs.settings.smtp_use_ssl,
                    fail_silently=False,
                    timeout=10,
                )
            else:
                backend = get_mail_backend(timeout=10)

            email = EmailMessage(
                subject=_('Eventyay system - test email'),
                body=_('This is a test email from your Eventyay system email configuration.'),
                from_email=mail_from,
                to=recipients,
                connection=backend,
            )
            email.send(fail_silently=False)
        except UnicodeEncodeError:
            # Stored credentials or recipient may contain non-ASCII (e.g. NBSP from clipboard).
            logger.warning(
                'Admin SMTP test failed — credentials or recipient contain non-ASCII characters (from=%s)',
                mail_from,
            )
            return self._respond(
                request,
                'error',
                _(
                    'SMTP authentication or email sending failed because the password, '
                    'username, or recipient address contains an invisible non-ASCII '
                    'character (e.g. a no-break space pasted from the clipboard). '
                    'Please verify these fields and try again.'
                ),
            )
        except HTTPError as e:
            logger.exception('Admin SendGrid test failed (from=%s)', mail_from)
            return self._respond(
                request,
                'error',
                _('SendGrid test email failed to connect or send. HTTP Error: %(err)s') % {'err': e},
            )
        except (smtplib.SMTPException, OSError) as e:
            logger.exception('Admin SMTP test failed (from=%s)', mail_from)
            return self._respond(
                request,
                'error',
                _('Test email failed to connect or send: %(err)s') % {'err': e},
            )

        recipients_str = ', '.join(recipients)
        logger.info('Admin test email sent to %d recipient(s)', len(recipients))
        return self._respond(
            request,
            'success',
            _('Test email sent to %(email)s — check inbox.') % {'email': recipients_str},
        )


class LogDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        le = get_object_or_404(LogEntry, pk=request.GET.get('pk'))
        return JsonResponse({'data': le.parsed_data})


class PaymentDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        p = get_object_or_404(OrderPayment, pk=request.GET.get('pk'))
        return JsonResponse({'data': p.info_data})


class RefundDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        p = get_object_or_404(OrderRefund, pk=request.GET.get('pk'))
        return JsonResponse({'data': p.info_data})
