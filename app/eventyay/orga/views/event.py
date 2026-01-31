from pathlib import Path

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.forms.models import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View
from django_context_decorator import context
from django_scopes import scope, scopes_disabled
from formtools.wizard.views import SessionWizardView

from eventyay.common.forms import I18nEventFormSet, I18nFormSet
from eventyay.base.models import LogEntry
from eventyay.common.text.phrases import phrases
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    PermissionRequired,
    SensibleBackWizardMixin,
)
from eventyay.base.models import Event, Team, TeamInvite
from eventyay.orga.forms import EventForm
from eventyay.orga.forms.event import (
    MailSettingsForm,
    ReviewPhaseForm,
    ReviewScoreCategoryForm,
    ReviewSettingsForm,
    WidgetGenerationForm,
    WidgetSettingsForm,
)
from eventyay.person.forms import UserForm
from eventyay.base.models import User
from eventyay.base.models import ReviewPhase, ReviewScoreCategory
from eventyay.submission.tasks import recalculate_all_review_scores


class EventSettingsPermission(EventPermissionRequired):
    permission_required = 'base.update_event'
    write_permission_required = 'base.update_event'

    @property
    def permission_object(self):
        return self.request.event


class EventDetail(EventSettingsPermission, ActionFromUrl, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'orga/settings/form.html'

    def get_object(self, queryset=None):
        return self.object

    @cached_property
    def object(self):
        return self.request.event

    def get_form_kwargs(self, *args, **kwargs):
        response = super().get_form_kwargs(*args, **kwargs)
        response['is_administrator'] = self.request.user.is_administrator
        return response

    @context
    def tablist(self):
        return {
            'display': _('Display settings'),
            'texts': _('Texts'),
        }

    def get_success_url(self) -> str:
        return self.object.orga_urls.settings

    @transaction.atomic
    def form_valid(self, form):
        result = super().form_valid(form)

        form.instance.log_action('eventyay.event.update', person=self.request.user, orga=True)
        messages.success(self.request, phrases.base.saved)
        return result


class EventLive(EventSettingsPermission, TemplateView):
    template_name = 'orga/event/live.html'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        warnings = []
        suggestions = []
        # TODO: move to signal
        if not self.request.event.cfp.text or len(str(self.request.event.cfp.text)) < 50:
            warnings.append(
                {
                    'text': _('The CfP doesn’t have a full text yet.'),
                    'url': self.request.event.cfp.urls.text,
                }
            )
        # TODO: test that mails can be sent
        if (
            self.request.event.get_feature_flag('use_tracks')
            and self.request.event.cfp.request_track
            and self.request.event.tracks.count() < 2
        ):
            suggestions.append(
                {
                    'text': _(
                        'You want submitters to choose the tracks for their proposals, but you do not offer tracks for selection. Add at least one track!'
                    ),
                    'url': self.request.event.cfp.urls.tracks,
                }
            )
        if self.request.event.submission_types.count() == 1:
            suggestions.append(
                {
                    'text': _('You have configured only one session type so far.'),
                    'url': self.request.event.cfp.urls.types,
                }
            )
        if not self.request.event.talkquestions.exists():
            suggestions.append(
                {
                    'text': _('You have configured no custom fields yet.'),
                    'url': self.request.event.cfp.urls.new_question,
                }
            )
        result['warnings'] = warnings
        result['suggestions'] = suggestions
        result['private_testmode_talks'] = self.request.event.settings.get('private_testmode_talks', False, as_type=bool)
        result['talks_testmode'] = self.request.event.settings.get('talks_testmode', False, as_type=bool)
        result['talks_published'] = self.request.event.talks_published
        return result

    def post(self, request, *args, **kwargs):
        event = request.event
        if request.POST.get('talks_published') == 'true':
            if not event.live:
                messages.error(self.request, _('Publish the event before publishing talks.'))
                return redirect(event.orga_urls.live)
            with transaction.atomic():
                previous_private = event.private_testmode
                event.talks_published = True
                event.settings.private_testmode_talks = False
                event.private_testmode = event.settings.get('private_testmode_tickets', True, as_type=bool)
                event.save()
                if previous_private != event.private_testmode:
                    self.request.event.log_action(
                        'eventyay.event.private_testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )
            messages.success(self.request, _('Talk pages are now published.'))
        elif request.POST.get('talks_published') == 'false':
            with transaction.atomic():
                event.talks_published = False
                event.settings.private_testmode_talks = True
                event.private_testmode = True
                if event.settings.get('talks_testmode', False, as_type=bool):
                    event.settings.talks_testmode = False
                event.save()
            messages.success(self.request, _('Talk pages have been unpublished.'))
        elif request.POST.get('talk_testmode') == 'true':
            if not event.talks_published:
                messages.error(
                    self.request,
                    _('Talk pages must be published before enabling talk test mode.'),
                )
                return redirect(event.orga_urls.live)
            with transaction.atomic():
                previous_private = event.private_testmode
                event.settings.talks_testmode = True
                if event.settings.get('private_testmode_talks', False, as_type=bool):
                    event.settings.private_testmode_talks = False
                    event.private_testmode = event.settings.get('private_testmode_tickets', True, as_type=bool)
                event.save()
                if previous_private and not event.private_testmode:
                    self.request.event.log_action(
                        'eventyay.event.private_testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )
                self.request.event.log_action('eventyay.event.talk_testmode.activated', user=self.request.user, data={})
            messages.success(self.request, _('Talk pages are now in test mode!'))
        elif request.POST.get('talk_testmode') == 'false':
            with transaction.atomic():
                event.settings.talks_testmode = False
                event.save()
                self.request.event.log_action('eventyay.event.talk_testmode.deactivated', user=self.request.user, data={})
            messages.success(self.request, _('Talk pages are now in production mode.'))
        elif request.POST.get('private_testmode_talks_action'):
            enable = request.POST.get('private_testmode_talks_action') == 'enable'
            if enable and event.talks_published:
                messages.error(self.request, _('Private test mode cannot be enabled while talks are published.'))
                return redirect(event.orga_urls.live)
            with transaction.atomic():
                previous_private = event.private_testmode
                event.settings.private_testmode_talks = enable
                if enable:
                    event.private_testmode = True
                    event.settings.talks_testmode = False
                else:
                    event.private_testmode = event.settings.get('private_testmode_tickets', True, as_type=bool)
                if event.private_testmode and event.testmode:
                    event.testmode = False
                    self.request.event.log_action(
                        'eventyay.event.testmode.deactivated',
                        user=self.request.user,
                        data={'delete': False},
                    )
                event.save()
                if previous_private != event.private_testmode:
                    self.request.event.log_action(
                        'eventyay.event.private_testmode.activated' if event.private_testmode else 'eventyay.event.private_testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )
            messages.success(
                self.request,
                _('Private test mode is now enabled for talks.') if enable else _('Private test mode is now disabled for talks.'),
            )
        return redirect(event.orga_urls.live)


class EventHistory(EventSettingsPermission, ListView):
    template_name = 'orga/event/history.html'
    model = LogEntry
    context_object_name = 'log_entries'
    paginate_by = 200

    def get_queryset(self):
        return LogEntry.objects.filter(event=self.request.event)


class EventReviewSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = ReviewSettingsForm
    template_name = 'orga/settings/review.html'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.review_settings

    @context
    def tablist(self):
        return {
            'general': _('General information'),
            'scores': _('Review scoring'),
            'phases': _('Review phases'),
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.request.event.locales
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            phases = self.save_phases()
            scores = self.save_scores()
        except ValidationError as e:
            messages.error(self.request, e.message)
            return self.get(self.request, *self.args, **self.kwargs)
        if not phases or not scores:
            return self.get(self.request, *self.args, **self.kwargs)
        form.save()
        if self.scores_formset.has_changed():
            recalculate_all_review_scores.apply_async(
                kwargs={'event_id': self.request.event.pk},
                ignore_result=True,
            )
        return super().form_valid(form)

    @context
    @cached_property
    def phases_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewPhase,
            form=ReviewPhaseForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=ReviewPhase.objects.filter(event=self.request.event).select_related('event'),
            event=self.request.event,
            prefix='phase',
        )

    def save_phases(self):
        if not self.phases_formset.is_valid():
            return False

        with transaction.atomic():
            for form in self.phases_formset.initial_forms:
                # Deleting is handled elsewhere, so we skip it here
                if form.has_changed():
                    form.instance.event = self.request.event
                    form.save()

            extra_forms = [
                form
                for form in self.phases_formset.extra_forms
                if form.has_changed and not self.phases_formset._should_delete_form(form)
            ]
            for form in extra_forms:
                form.instance.event = self.request.event
                form.save()

            for form in self.phases_formset.deleted_forms:
                form.instance.delete()

            # Now that everything is saved, check for overlapping review phases,
            # and show an error message if any exist. Raise an exception to
            # get out of the transaction.
            self.request.event.reorder_review_phases()
            review_phases = list(self.request.event.review_phases.all().order_by('position'))
            for phase, next_phase in zip(review_phases, review_phases[1:]):
                if not phase.end:
                    raise ValidationError(_('Only the last review phase may be open-ended.'))
                if not next_phase.start:
                    raise ValidationError(_('All review phases except for the first one need a start date.'))
                if phase.end > next_phase.start:
                    raise ValidationError(
                        _(
                            "The review phases '{phase1}' and '{phase2}' overlap. "
                            'Please make sure that review phases do not overlap, then save again.'
                        ).format(phase1=phase.name, phase2=next_phase.name)
                    )
        return True

    @context
    @cached_property
    def scores_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewScoreCategory,
            form=ReviewScoreCategoryForm,
            formset=I18nEventFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=ReviewScoreCategory.objects.filter(event=self.request.event)
            .select_related('event')
            .prefetch_related('scores'),
            event=self.request.event,
            prefix='scores',
        )

    def save_scores(self):
        if not self.scores_formset.is_valid():
            return False
        weights_changed = False
        for form in self.scores_formset.initial_forms:
            # Deleting is handled elsewhere, so we skip it here
            if form.has_changed():
                if 'weight' in form.changed_data:
                    weights_changed = True
                form.instance.event = self.request.event
                form.save()

        extra_forms = [
            form
            for form in self.scores_formset.extra_forms
            if form.has_changed and not self.scores_formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.event = self.request.event
            form.save()

        for form in self.scores_formset.deleted_forms:
            if not form.instance.is_independent:
                weights_changed = True
            if form.instance.pk:
                form.instance.scores.all().delete()
                form.instance.delete()

        if weights_changed:
            ReviewScoreCategory.recalculate_scores(self.request.event)
        return True


class PhaseActivate(EventSettingsPermission, View):
    def get_object(self):
        return get_object_or_404(ReviewPhase, event=self.request.event, pk=self.kwargs.get('pk'))

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        phase = self.get_object()
        phase.activate()
        return redirect(self.request.event.orga_urls.review_settings)


class EventMailSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = 'orga/settings/mail.html'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.mail_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['locales'] = self.request.event.locales
        return kwargs

    def form_valid(self, form):
        form.save()

        if self.request.POST.get('test', '0').strip() == '1':
            backend = self.request.event.get_mail_backend(force_custom=True)
            try:
                backend.test(self.request.event.mail_settings['mail_from'])
            except Exception as e:
                messages.warning(
                    self.request,
                    _('An error occurred while contacting the SMTP server: %s') % str(e),
                )
            else:  # pragma: no cover
                if form.cleaned_data.get('smtp_use_custom'):
                    messages.success(
                        self.request,
                        _(
                            'Yay, your changes have been saved and the connection attempt to '
                            'your SMTP server was successful.'
                        ),
                    )
                else:
                    messages.success(
                        self.request,
                        _(
                            'We’ve been able to contact the SMTP server you configured. '
                            'Remember to check the “use custom SMTP server” checkbox, '
                            'otherwise your SMTP server will not be used.'
                        ),
                    )
        else:
            messages.success(self.request, phrases.base.saved)

        return super().form_valid(form)


class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    @context
    @cached_property
    def invitation(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get('code'))

    @context
    def password_reset_link(self):
        return reverse('orga:auth.reset')

    def post(self, *args, **kwargs):
        if not self.request.user.is_anonymous:
            self.accept_invite(self.request.user)
            return redirect(reverse('orga:event.list'))
        return super().post(*args, **kwargs)

    def form_valid(self, form):
        form.save()
        user = User.objects.filter(pk=form.cleaned_data.get('user_id')).first()
        if not user:
            messages.error(
                self.request,
                _('There was a problem with your authentication. Please contact the organizer for further help.'),
            )
            return redirect(self.request.event.urls.base)

        self.accept_invite(user)
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(reverse('orga:event.list'))

    @transaction.atomic()
    def accept_invite(self, user):
        invite = self.invitation
        invite.team.members.add(user)
        invite.team.save()
        invite.team.organizer.log_action('eventyay.invite.orga.accept', person=user, orga=True)
        messages.info(self.request, _('You are now part of the team!'))
        invite.delete()


class EventDelete(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = 'base.administrator_user'
    model = Event
    action_text = (
        _(
            'ALL related data, such as proposals, and speaker profiles, and '
            'uploads, will also be deleted and cannot be restored.'
        )
        + ' '
        + phrases.base.delete_warning
    )

    def get_object(self):
        return self.request.event

    def action_object_name(self):
        return ngettext_lazy('Event', 'Events', 1) + f': {self.get_object().name}'

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.settings

    def post(self, request, *args, **kwargs):
        self.get_object().shred(person=self.request.user)
        return redirect(reverse('orga:event.list'))

@method_decorator(csp_update({'SCRIPT_SRC': "'self' 'unsafe-eval'"}), name='dispatch')
class WidgetSettings(EventSettingsPermission, FormView):
    form_class = WidgetSettingsForm
    template_name = 'orga/settings/widget.html'

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['extra_form'] = WidgetGenerationForm(instance=self.request.event)
        return result

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.widget_settings
