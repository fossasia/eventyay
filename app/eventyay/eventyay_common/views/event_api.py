"""Dedicated event API information and token management views."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from eventyay.base.meetup import is_meetup_event
from eventyay.base.models import Team, UserApiToken
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views.event import EventSettingsViewMixin
from eventyay.control.views.organizer import TokenForm
from eventyay.eventyay_common.api_catalog import (
    API_PAGE_PERMISSIONS,
    access_levels,
    build_api_catalog,
    docs_urls,
    event_has_tickets_component,
    event_has_talks_component,
    permission_label,
    tickets_api_base,
    talks_api_base,
)


class EventAPIView(EventSettingsViewMixin, EventPermissionRequiredMixin, TemplateView):
    """Central API overview, docs, and token management for an event."""

    template_name = 'eventyay_common/event/api.html'
    # Any API-related event permission is enough to open the page; endpoints
    # are still filtered individually by read/write permissions.
    permission = API_PAGE_PERMISSIONS

    def get_success_url(self):
        return reverse(
            'eventyay_common:event.api',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    @cached_property
    def can_manage_team_tokens(self) -> bool:
        return self.request.user.has_event_permission(
            self.request.organizer,
            self.request.event,
            'can_change_teams',
            request=self.request,
        ) or bool(getattr(self.request.user, 'is_administrator', False))

    def get_event_teams(self):
        event = self.request.event
        return (
            Team.objects.filter(organizer=event.organizer)
            .filter(Q(all_events=True) | Q(limit_events=event))
            .distinct()
            .prefetch_related(
                Prefetch(
                    'tokens',
                    queryset=TeamAPIToken.objects.filter(active=True).order_by('name'),
                    to_attr='active_token_list',
                )
            )
            .order_by('name')
        )

    def get_user_api_tokens(self):
        return (
            UserApiToken.objects.active()
            .filter(user=self.request.user, events=self.request.event)
            .prefetch_related('events')
            .order_by('-created')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event
        teams = list(self.get_event_teams())
        for team in teams:
            team.token_form = TokenForm(prefix=f'token-{team.pk}')
            # Tokens inherit the team's permissions; surface the effective set.
            # permission_set() is a method; permission_set_display incorrectly
            # treats it as a property in some code paths, so build labels here.
            team.effective_permission_labels = sorted(
                filter(
                    None,
                    (permission_label(perm) for perm in team.permission_set()),
                )
            )
        show_tickets = event_has_tickets_component(event)
        show_talks = event_has_talks_component(event)
        ctx.update(
            {
                'endpoint_groups': build_api_catalog(self.request, event),
                'access_levels': access_levels(),
                'docs_urls': docs_urls(),
                'tickets_api_base': tickets_api_base(event) if show_tickets else None,
                'talks_api_base': talks_api_base(event) if show_talks else None,
                'show_tickets_api': show_tickets,
                'show_talks_api': show_talks,
                'can_manage_team_tokens': self.can_manage_team_tokens,
                'event_teams': teams,
                'user_api_tokens': self.get_user_api_tokens(),
                'teams_url': reverse(
                    'eventyay_common:organizer.teams',
                    kwargs={'organizer': event.organizer.slug},
                )
                + '?section=permissions',
                'user_token_settings_url': reverse('orga:user.view'),
                'is_meetup': is_meetup_event(event),
            }
        )
        return ctx

    def post(self, request, *args, **kwargs):
        if not self.can_manage_team_tokens:
            messages.error(request, _('You do not have permission to manage API tokens.'))
            return redirect(self.get_success_url())

        action = request.POST.get('token_action')
        if action == 'create':
            return self._create_token(request)
        if action == 'revoke':
            return self._revoke_token(request)

        messages.error(request, _('Unknown action.'))
        return redirect(self.get_success_url())

    def _get_team(self, request) -> Team | None:
        try:
            team_id = int(request.POST.get('team_id', ''))
        except (TypeError, ValueError):
            return None
        return self.get_event_teams().filter(pk=team_id).first()

    def _create_token(self, request):
        team = self._get_team(request)
        if not team:
            messages.error(request, _('Invalid team selected.'))
            return redirect(self.get_success_url())

        form = TokenForm(data=request.POST, prefix=f'token-{team.pk}')
        if not form.is_valid() or not form.cleaned_data.get('name'):
            messages.error(request, _('Please provide a token name.'))
            return redirect(self.get_success_url() + '#tokens')

        with transaction.atomic():
            token = team.tokens.create(name=form.cleaned_data['name'])
            team.log_action(
                'eventyay.team.token.created',
                user=request.user,
                data={'name': token.name, 'id': token.pk, 'event': request.event.slug},
            )
        messages.success(
            request,
            _(
                'A new API token has been created with the following secret: {}\n'
                'Please copy this secret to a safe place. You will not be able to '
                'view it again here.'
            ).format(token.token),
        )
        return redirect(self.get_success_url() + '#tokens')

    def _revoke_token(self, request):
        team = self._get_team(request)
        if not team:
            messages.error(request, _('Invalid team selected.'))
            return redirect(self.get_success_url())

        try:
            token_id = int(request.POST.get('token_id', ''))
            token = team.tokens.get(pk=token_id, active=True)
        except (TypeError, ValueError, TeamAPIToken.DoesNotExist):
            messages.error(request, _('Invalid token selected.'))
            return redirect(self.get_success_url() + '#tokens')

        with transaction.atomic():
            token.active = False
            token.save(update_fields=['active'])
            team.log_action(
                'eventyay.team.token.deleted',
                user=request.user,
                data={'name': token.name, 'event': request.event.slug},
            )
        messages.success(request, _('The token has been revoked.'))
        return redirect(self.get_success_url() + '#tokens')
