import logging
import nh3
import uuid
from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, Subquery, OuterRef, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View
from urllib.parse import urlencode

from eventyay.base.email import get_available_placeholders
from eventyay.base.i18n import language
from eventyay.base.models.base import CachedFile
from eventyay.base.models.event import Event
from eventyay.base.models.orders import Order, OrderPosition
from eventyay.base.services.mail import TolerantDict
from eventyay.base.templatetags.rich_text import markdown_compile_email
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.helpers.timezone import get_browser_timezone, attach_timezone_to_naive_clock_time
from eventyay.plugins.sendmail.forms import EmailQueueEditForm
from eventyay.plugins.sendmail.mixins import CopyDraftMixin, QueryFilterOrderingMixin
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter, EmailQueueToUser
from eventyay.plugins.sendmail.tasks import send_queued_mail
from eventyay.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from .forms import MailContentSettingsForm, TeamMailForm


from . import forms


logger = logging.getLogger(__name__)


class BulkReplyToMixin:
    """Mixin for bulk email views to resolve Reply-To address."""
    
    def _get_reply_to_for_bulk_email(self):
        from eventyay.common.mail import get_reply_to_address
        return get_reply_to_address(
            self.request.event
        )


class ComposeMailChoice(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/compose_choice.html'


class SenderView(EventPermissionRequiredMixin, CopyDraftMixin, BulkReplyToMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_form.html'
    permission = 'can_change_orders'
    form_class = forms.MailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        self.load_copy_draft(self.request, kwargs)
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('We could not queue the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        qs = Order.objects.filter(event=self.request.event)
        statusq = Q(status__in=form.cleaned_data['order_status'])
        if 'overdue' in form.cleaned_data['order_status']:
            statusq |= Q(status=Order.STATUS_PENDING, expires__lt=now())
        if 'pa' in form.cleaned_data['order_status']:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=True)
        if 'na' in form.cleaned_data['order_status']:
            statusq |= Q(status=Order.STATUS_PENDING, require_approval=False)
        orders = qs.filter(statusq)

        opq = OrderPosition.objects.filter(
            order=OuterRef('pk'),
            canceled=False,
            product_id__in=[p.pk for p in form.cleaned_data.get('products')],
        )

        if form.cleaned_data.get('has_filter_checkins'):
            ql = []
            if form.cleaned_data.get('not_checked_in'):
                ql.append(Q(checkins__list_id=None))
            if form.cleaned_data.get('checkin_lists'):
                ql.append(
                    Q(
                        checkins__list_id__in=[i.pk for i in form.cleaned_data.get('checkin_lists', [])],
                    )
                )
            if len(ql) == 2:
                opq = opq.filter(ql[0] | ql[1])
            elif ql:
                opq = opq.filter(ql[0])
            else:
                opq = opq.none()

        if form.cleaned_data.get('subevent'):
            opq = opq.filter(subevent=form.cleaned_data.get('subevent'))
        if form.cleaned_data.get('subevents_from'):
            opq = opq.filter(subevent__date_from__gte=form.cleaned_data.get('subevents_from'))
        if form.cleaned_data.get('subevents_to'):
            opq = opq.filter(subevent__date_from__lt=form.cleaned_data.get('subevents_to'))
        if form.cleaned_data.get('order_created_from') or form.cleaned_data.get('order_created_to'):
            browser_tz = get_browser_timezone(form.cleaned_data.get('browser_timezone'))

            def attach_timezone(dt_value):
                return attach_timezone_to_naive_clock_time(dt_value, browser_tz)

            if form.cleaned_data.get('order_created_from'):
                opq = opq.filter(order__datetime__gte=attach_timezone(form.cleaned_data['order_created_from']))
            if form.cleaned_data.get('order_created_to'):
                opq = opq.filter(order__datetime__lt=attach_timezone(form.cleaned_data['order_created_to']))

        orders = orders.annotate(match_pos=Exists(opq)).filter(match_pos=True).distinct()

        if not orders:
            messages.error(self.request, _('There are no orders matching this selection.'))
            return self.get(self.request, *self.args, **self.kwargs)

        if self.request.POST.get('action') == 'preview':
            self.output = {}
            for l in self.request.event.settings.locales:
                with language(l, self.request.event.settings.region):
                    context_dict = TolerantDict()
                    for k, v in get_available_placeholders(
                        self.request.event, ['event', 'order', 'position_or_address']
                    ).items():
                        context_dict[k] = '<span class="placeholder" title="{}">{}</span>'.format(
                            _('This value will be replaced based on dynamic parameters.'),
                            v.render_sample(self.request.event),
                        )

                    subject = nh3.clean(form.cleaned_data['subject'].localize(l), tags=set())
                    preview_subject = subject.format_map(context_dict)
                    message = form.cleaned_data['message'].localize(l)
                    preview_text = markdown_compile_email(message.format_map(context_dict))

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=preview_subject),
                        'html': preview_text,
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        qm = EmailQueue.objects.create(
            event=self.request.event,
            user=self.request.user,
            subject=form.cleaned_data['subject'].data,
            message=form.cleaned_data['message'].data,
            attachments=[form.cleaned_data['attachment'].id] if form.cleaned_data.get('attachment') else [],
            locale=self.request.event.settings.locale,
            reply_to=self._get_reply_to_for_bulk_email() or '',
            bcc=self.request.event.settings.get('mail_bcc'),
            composing_for=ComposingFor.ATTENDEES,
        )

        EmailQueueFilter.objects.create(
            mail=qm,
            recipients=form.cleaned_data['recipients'],
            order_status=form.cleaned_data['order_status'],
            orders=list(orders.values_list('pk', flat=True)),
            products=[i.pk for i in form.cleaned_data.get('products')],
            checkin_lists=[cl.pk for cl in form.cleaned_data.get('checkin_lists')],
            has_filter_checkins=form.cleaned_data.get('has_filter_checkins'),
            not_checked_in=form.cleaned_data.get('not_checked_in'),
            subevent=form.cleaned_data.get('subevent').pk if form.cleaned_data.get('subevent') else None,
            subevents_from=form.cleaned_data.get('subevents_from'),
            subevents_to=form.cleaned_data.get('subevents_to'),
            order_created_from=form.cleaned_data.get('order_created_from'),
            order_created_to=form.cleaned_data.get('order_created_to'),
        )

        qm.populate_to_users()

        messages.success(
            self.request,
            _('Your email has been sent to the outbox.')
        )

        return redirect(
            reverse('plugins:sendmail:send', kwargs={
                'event': self.request.event.slug,
                'organizer': self.request.event.organizer.slug,
            }) + '?' + urlencode({
                'organizer': self.request.event.organizer.slug,
            })
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['output'] = getattr(self, 'output', None)
        return ctx


class MailTemplatesView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    template_name = 'pretixplugins/sendmail/mail_templates.html'
    form_class = MailContentSettingsForm
    permission = 'can_change_event_settings'

    def form_invalid(self, form):
        messages.error(
            self.request,
            _('We could not save your changes. See below for details.'),
        )
        return super().form_invalid(form)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)

        form.save()
        if form.has_changed():
            self.request.event.log_action(
                'eventyay.event.settings',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return redirect(reverse(
            'plugins:sendmail:templates',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        ))


class OutboxListView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = EmailQueue
    context_object_name = 'mails'
    template_name = 'pretixplugins/sendmail/outbox_list.html'
    permission_required = 'can_change_orders'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        query = self.request.GET.get('q', '')
        ordering = self.request.GET.get('ordering')

        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
        ]
        ctx['current_ordering'] = ordering
        ctx['query'] = query

        MAX_ERRORS_TO_SHOW = 2
        for mail in ctx['mails']:
            mail.recipient_emails_display = ", ".join(mail.get_recipient_emails())
            all_recipients = mail.recipients.all()
            errors = [r for r in all_recipients if r.error]
            mail.recipient_errors_preview = errors[:MAX_ERRORS_TO_SHOW]
            mail.recipient_error_count = len(errors)

        return ctx

    def get_queryset(self):
        first_recipient_email = EmailQueueToUser.objects.filter(
            mail=OuterRef('pk')
        ).order_by('id').values('email')[:1]

        base_qs = self.model.objects.filter(
            event=self.request.event,
            sent_at__isnull=True
        ).select_related('event', 'user').prefetch_related('recipients').annotate(
            first_recipient_email=Subquery(first_recipient_email)
        )

        return self.get_filtered_queryset(base_qs)


class SendEmailQueueView(EventPermissionRequiredMixin, View):
    permission_required = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        mail = get_object_or_404(
            EmailQueue,
            event=request.event,
            pk=kwargs['pk']
        )

        if mail.sent_at:
            messages.warning(request, _('This mail has already been sent.'))
        else:
            # Enqueue the Celery task
            send_queued_mail.apply_async(args=[request.event.pk, mail.pk])
            messages.success(
                request,
                _('The mail has been queued for sending.')
            )

        return HttpResponseRedirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug,
        }))


class EditEmailQueueView(EventPermissionRequiredMixin, UpdateView):
    model = EmailQueue
    form_class = EmailQueueEditForm
    template_name = 'pretixplugins/sendmail/outbox_form.html'
    permission_required = 'can_change_orders'

    def get_object(self, queryset=None):
        return get_object_or_404(
            EmailQueue, event=self.request.event, pk=self.kwargs["pk"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['read_only'] = bool(self.object.sent_at)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['read_only'] = bool(self.object.sent_at)

        if self.object.attachments:
            ctx['attachments_files'] = CachedFile.objects.filter(
                id__in=self.object.attachments
            )
        else:
            ctx['attachments_files'] = []

        ctx['output'] = getattr(self, 'output', None)

        return ctx

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        if form.instance.sent_at:
            messages.error(self.request, _('This email has already been sent and cannot be edited.'))
            return self.form_invalid(form)

        if self.request.POST.get('action') == 'preview':
            self.output = {}
            event = self.request.event
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            if form.instance.composing_for == ComposingFor.TEAMS:
                base_placeholders = ['event', 'team']
            else:
                base_placeholders = ['event', 'order', 'position_or_address']

            for l in event.settings.locales:
                with language(l, event.settings.region):
                    context_dict = {
                        k: f"""<span class="placeholder" title="{
                            _('This value will be replaced based on dynamic parameters.')
                            }">{v.render_sample(self.request.event)}</span>"""
                        for k, v in get_available_placeholders(event, base_placeholders).items()
                    }

                    try:
                        subject_preview = subject.localize(l).format_map(context_dict)
                    except KeyError as e:
                        form.add_error('subject', _('Invalid placeholder(s): {}').format(str(e)))
                        return self.form_invalid(form)

                    try:
                        message_preview = message.localize(l).format_map(context_dict)
                    except KeyError as e:
                        form.add_error('message', _('Invalid placeholder(s): {}').format(str(e)))
                        return self.form_invalid(form)

                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': markdown_compile_email(message_preview),
                    }

            return self.get(self.request, *self.args, **self.kwargs)

        response = super().form_valid(form)
        messages.success(self.request, _('Your changes have been saved.'))
        return response

    def get_success_url(self):
        return reverse('plugins:sendmail:outbox', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class DeleteEmailQueueView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/delete_confirmation.html'

    @cached_property
    def mail(self):
        return get_object_or_404(
            EmailQueue, event=self.request.event, pk=self.kwargs['pk']
        )

    def question(self):
        return _("Do you really want to delete this mail?")

    def post(self, request, *args, **kwargs):
        mail = self.mail
        if mail.sent_at:
            messages.error(
                request,
                _("This mail has already been sent and cannot be deleted.")
            )
        else:
            EmailQueueFilter.objects.filter(mail=mail).delete()
            EmailQueueToUser.objects.filter(mail=mail).delete()
            mail.delete()

            messages.success(
                request,
                _("The mail and its related data have been deleted.")
            )

        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class PurgeEmailQueuesView(EventPermissionRequiredMixin, TemplateView):
    permission_required = 'can_change_orders'
    template_name = 'pretixplugins/sendmail/purge_confirmation.html'

    def get_permission_object(self):
        return self.request.event

    def question(self):
        count = EmailQueue.objects.filter(event=self.request.event, sent_at__isnull=True).count()
        return ngettext_lazy(
            "Do you really want to purge the mail?",
            "Do you really want to purge {count} mails?",
            count
        ).format(count=count)

    def post(self, request, *args, **kwargs):
        mails = EmailQueue.objects.filter(event=request.event, sent_at__isnull=True)

        EmailQueueFilter.objects.filter(mail__in=mails).delete()
        EmailQueueToUser.objects.filter(mail__in=mails).delete()
        count = mails.count()
        mails.delete()

        messages.success(
            request,
            ngettext_lazy(
                "One mail has been discarded.",
                "{count} mails have been discarded.",
                count
            ).format(count=count)
        )

        return redirect(reverse('plugins:sendmail:outbox', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))


class SentMailView(EventPermissionRequiredMixin, QueryFilterOrderingMixin, ListView):
    model = EmailQueue
    context_object_name = "mails"
    template_name = "pretixplugins/sendmail/sent_list.html"
    permission_required = "can_change_orders"
    paginate_by = 25

    def get_queryset(self):
        first_recipient_email = EmailQueueToUser.objects.filter(
            mail=OuterRef('pk')
        ).order_by('pk').values('email')[:1]

        base_qs = self.model.objects.filter(
            event=self.request.event,
            sent_at__isnull=False
        ).select_related('event', 'user').prefetch_related('recipients').annotate(
            first_recipient_email=Subquery(first_recipient_email)
        )

        return self.get_filtered_queryset(base_qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        query = self.request.GET.get('q', '')
        ordering = self.request.GET.get('ordering')

        ctx['headers'] = [
            ('subject', _('Subject')),
            ('recipient', _('To')),
            ('created', _('Sent at')),
        ]
        ctx['current_ordering'] = ordering
        ctx['query'] = query

        MAX_RECIPIENTS_TO_SHOW = 3
        for mail in ctx['mails']:
            users = EmailQueueToUser.objects.filter(mail=mail).order_by('pk')[:MAX_RECIPIENTS_TO_SHOW]
            mail.recipient_preview = [u.email or u.user_display or u.order_code for u in users]
            mail.recipient_total = EmailQueueToUser.objects.filter(mail=mail).count()

        return ctx


class ComposeTeamsMail(EventPermissionRequiredMixin, CopyDraftMixin, BulkReplyToMixin, FormView):
    template_name = 'pretixplugins/sendmail/send_team_form.html'
    permission = 'can_change_orders'
    form_class = TeamMailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        self.load_copy_draft(self.request, kwargs, team_mode=True)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['output'] = getattr(self, 'output', None)

        return ctx

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save the email. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        event = self.request.event
        user = self.request.user
        subject = form.cleaned_data['subject']
        message = form.cleaned_data['message']

        self.output = {}
        for l in event.settings.locales:
            with language(l, event.settings.region):
                context_dict = {
                    k: f"""<span class="placeholder" title="{
                        _('This value will be replaced based on dynamic parameters.')
                        }">{v.render_sample(self.request.event)}</span>"""
                    for k, v in get_available_placeholders(event, ['event', 'team']).items()
                }

                try:
                    subject_preview = subject.localize(l).format_map(context_dict)
                except KeyError as e:
                    form.add_error('subject', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                try:
                    message_preview = message.localize(l).format_map(context_dict)
                except KeyError as e:
                    form.add_error('message', _('Invalid placeholder(s): {}').format(str(e)))
                    return self.form_invalid(form)

                if self.request.POST.get('action') == 'preview':
                    self.output[l] = {
                        'subject': _('Subject: {subject}').format(subject=subject_preview),
                        'html': markdown_compile_email(message_preview),
                    }

        if self.request.POST.get('action') == 'preview':
            return self.get(self.request, *self.args, **self.kwargs)

        sent_emails = set()
        recipients_list = []
        for team in form.cleaned_data['teams']:
            for member in team.members.all():
                if not member.email or member.email in sent_emails:
                    continue
                recipients_list.append({
                    "email": member.email,
                    "team": team.pk,
                    "orders": [],
                    "positions": [],
                    "products": [],
                    "sent": False,
                    "error": None
                })

                sent_emails.add(member.email)

        if not recipients_list:
            messages.error(self.request, _('There are no valid recipients for the selected teams.'))
            return self.form_invalid(form)

        # Create the EmailQueue instance
        mail_instance = EmailQueue.objects.create(
            event=event,
            user=user,
            composing_for=ComposingFor.TEAMS,
            subject=subject.data,
            message=message.data,
            locale=event.settings.locale,
            reply_to=self._get_reply_to_for_bulk_email() or '',
            bcc=event.settings.get('mail_bcc'),
            attachments=[form.cleaned_data['attachment'].id] if form.cleaned_data.get('attachment') else [],
        )

        # Create associated filter data for teams
        EmailQueueFilter.objects.create(
            mail=mail_instance,
            order_status=[],
            products=[],
            checkin_lists=[],
            has_filter_checkins=False,
            not_checked_in=False,
            subevent=None,
            subevents_from=None,
            subevents_to=None,
            order_created_from=None,
            order_created_to=None,
            orders=[],
            teams=[team.pk for team in form.cleaned_data['teams']],
        )

        # Create recipient entries for each team member
        recipient_objs = [
            EmailQueueToUser(
                mail=mail_instance,
                email=rec["email"],
                team=rec["team"],
                sent=rec["sent"],
                error=rec["error"]
            )
            for rec in recipients_list
        ]
        EmailQueueToUser.objects.bulk_create(recipient_objs)

        messages.success(
            self.request,
            _('Your email has been sent to the outbox.')
        )

        return redirect(reverse('plugins:sendmail:compose_email_teams', kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug
        }))
