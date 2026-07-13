from collections import OrderedDict

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from django_scopes.forms import SafeModelMultipleChoiceField

from eventyay.base.models.organizer import Team
from eventyay.base.models.track import Track
from eventyay.control.forms.event import SafeEventMultipleChoiceField


class TeamForm(forms.ModelForm):
    @scopes_disabled()
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        self.organizer = organizer
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by('-has_subevents', '-date_from')
        tracks_qs = (
            Track.objects.filter(event__organizer=organizer)
            .select_related('event')
            .order_by('-event__date_from', 'name')
        )
        self.fields['limit_tracks'].queryset = tracks_qs

        events_qs = organizer.events.all().order_by('-date_from', 'name')
        self._events_with_tracks = self._build_events_with_tracks(events_qs, tracks_qs)

        # Cache selected track IDs now (inside scopes_disabled context)
        # so the template can use them without scope issues
        if self.instance and self.instance.pk:
            self._selected_track_ids = set(self.instance.limit_tracks.values_list('pk', flat=True))
        else:
            self._selected_track_ids = set()

        has_teamshifts = False
        if apps.is_installed('teamshifts'):
            has_teamshifts = organizer.events.filter(plugins__contains='teamshifts').exists()

        self.teamshifts_plugin_enabled = has_teamshifts
        if has_teamshifts:
            TeamRole = apps.get_model('teamshifts', 'TeamRole')
            roles_qs = (
                TeamRole.objects.filter(event__organizer=organizer)
                .select_related('event')
                .order_by('-event__date_from', 'name')
            )
            self.fields['limit_teamshifts_roles'] = SafeModelMultipleChoiceField(
                queryset=roles_qs,
                required=False,
                widget=forms.CheckboxSelectMultiple(
                    attrs={'class': 'scrolling-multiple-choice scrolling-multiple-choice-large'}
                ),
            )
            self._events_with_teamshifts_roles = self._build_events_with_tracks(organizer.events.all(), roles_qs)

            if self.instance and self.instance.pk:
                self.initial['limit_teamshifts_roles'] = self.instance.limit_teamshifts_roles
        else:
            self._events_with_teamshifts_roles = []

    @staticmethod
    def _build_events_with_tracks(events_qs, tracks_qs):
        """Build per-event track groups for the organiser team permissions UI.

        Includes every organiser event so the UI can show an empty state when
        an event has no tracks. Tracks are grouped using select_related data
        from ``tracks_qs`` to avoid N+1 queries.
        """
        events = OrderedDict()
        for event in events_qs:
            events[event.pk] = {
                'id': event.pk,
                'name': str(event.name),
                'slug': event.slug,
                'tracks': [],
            }
        for track in tracks_qs:
            evt_pk = track.event_id
            if evt_pk not in events:
                event = track.event
                events[evt_pk] = {
                    'id': evt_pk,
                    'name': str(event.name),
                    'slug': event.slug,
                    'tracks': [],
                }
            events[evt_pk]['tracks'].append(
                {
                    'id': track.pk,
                    'name': str(track.name),
                }
            )
        return list(events.values())

    @property
    def events_with_tracks(self):
        """Return events with their tracks for use in templates."""
        return self._events_with_tracks

    @property
    def events_with_teamshifts_roles(self):
        """Return events with their teamshifts roles for use in templates."""
        return self._events_with_teamshifts_roles

    @property
    def selected_track_ids(self):
        """Return a set of currently selected track PKs for pre-checking checkboxes."""
        if self.is_bound:
            # Form was submitted — get from POST data (uses prefixed field name)
            field_name = self.add_prefix('limit_tracks')
            if hasattr(self.data, 'getlist'):
                values = self.data.getlist(field_name)
            else:
                raw = self.data.get(field_name, [])
                values = raw if isinstance(raw, (list, tuple)) else [raw]
            try:
                return {int(v) for v in values if v not in (None, '')}
            except (ValueError, TypeError):
                return set()
        # On GET (page load) — return cached DB values
        return self._selected_track_ids

    @property
    def has_any_tracks(self):
        """Whether any organiser event currently has tracks configured."""
        return any(event_data['tracks'] for event_data in self._events_with_tracks)

    @property
    def selected_teamshifts_role_ids(self):
        """Return a set of currently selected teamshifts role PKs for pre-checking checkboxes."""
        if self.is_bound:
            field_name = self.add_prefix('limit_teamshifts_roles')
            values = self.data.getlist(field_name)
            try:
                return {int(v) for v in values}
            except (ValueError, TypeError):
                return set()
        if self.instance and self.instance.pk:
            return set(self.instance.limit_teamshifts_roles)
        return set()

    class Meta:
        model = Team
        fields = [
            'name',
            'all_events',
            'limit_events',
            'can_create_events',
            'can_change_teams',
            'can_change_organizer_settings',
            'can_manage_gift_cards',
            'can_change_event_settings',
            'can_change_items',
            'can_view_orders',
            'can_change_orders',
            'can_manage_bank_transfers',
            'can_checkin_orders',
            'can_view_vouchers',
            'can_change_vouchers',
            'can_change_submissions',
            'is_reviewer',
            'force_hide_speaker_names',
            'force_hide_speaker_emails',
            'limit_tracks',
            'can_change_exhibition_proposals',
            'is_exhibition_reviewer',
            'hide_exhibition_applicant_emails',
            'can_video_create_stages',
            'can_video_create_channels',
            'can_video_direct_message',
            'can_video_manage_announcements',
            'can_video_view_users',
            'can_video_manage_users',
            'can_video_manage_rooms',
            'can_video_manage_polls_questions',
            'can_video_manage_kiosks',
            'can_video_manage_configuration',
            'can_teamshifts_manage_applicants',
            'can_teamshifts_create_shifts',
            'can_teamshifts_create_roles',
            'can_teamshifts_send_emails',
            'can_teamshifts_view_email_addresses',
            'all_teamshifts_roles',
        ]
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(
                attrs={
                    'data-inverse-dependency': '#id_all_events',
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
            'limit_tracks': forms.CheckboxSelectMultiple(
                attrs={
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
        }
        field_classes = {
            'limit_events': SafeEventMultipleChoiceField,
            'limit_tracks': SafeModelMultipleChoiceField,
        }

    @scopes_disabled()
    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)

    def clean(self):
        data = super().clean()
        all_events = data.get('all_events')
        limit_events = data.get('limit_events')
        if not all_events and not limit_events:
            error = forms.ValidationError(
                _('Please either pick some events for this team, or grant access to all your events!')
            )
            self.add_error('limit_events', error)

        all_teamshifts_roles = data.get('all_teamshifts_roles')
        limit_teamshifts_roles = data.get('limit_teamshifts_roles')
        if getattr(self, 'teamshifts_plugin_enabled', False):
            if not all_teamshifts_roles and not limit_teamshifts_roles:
                self.add_error(
                    'limit_teamshifts_roles',
                    forms.ValidationError(_('Please select at least one role if not granting access to all roles.')),
                )

            # SafeModelMultipleChoiceField returns a queryset. Convert to list of PKs for the JSONField
            if 'limit_teamshifts_roles' in data and hasattr(data['limit_teamshifts_roles'], 'values_list'):
                data['limit_teamshifts_roles'] = list(data['limit_teamshifts_roles'].values_list('pk', flat=True))

        permissions = (
            'can_create_events',
            'can_change_teams',
            'can_change_organizer_settings',
            'can_manage_gift_cards',
            'can_change_event_settings',
            'can_change_items',
            'can_view_orders',
            'can_change_orders',
            'can_manage_bank_transfers',
            'can_checkin_orders',
            'can_view_vouchers',
            'can_change_vouchers',
            'can_change_submissions',
            'is_reviewer',
            'can_change_exhibition_proposals',
            'is_exhibition_reviewer',
            'can_video_create_stages',
            'can_video_create_channels',
            'can_video_direct_message',
            'can_video_manage_announcements',
            'can_video_view_users',
            'can_video_manage_users',
            'can_video_manage_rooms',
            'can_video_manage_polls_questions',
            'can_video_manage_kiosks',
            'can_video_manage_configuration',
            'can_teamshifts_manage_applicants',
            'can_teamshifts_create_shifts',
            'can_teamshifts_create_roles',
            'can_teamshifts_send_emails',
            'can_teamshifts_view_email_addresses',
        )
        if not any(data.get(permission) for permission in permissions):
            error = forms.ValidationError(_('Please pick at least one permission for this team!'))
            self.add_error(None, error)

        if data.get('can_change_orders'):
            data['can_view_orders'] = True
        if data.get('can_change_vouchers'):
            data['can_view_vouchers'] = True
        if data.get('can_manage_bank_transfers'):
            data['can_view_orders'] = True
        if self.instance.pk and not data['can_change_teams']:
            if (
                not self.instance.organizer.teams.exclude(pk=self.instance.pk)
                .filter(can_change_teams=True, members__isnull=False)
                .exists()
            ):
                raise ValidationError(
                    _(
                        'The changes could not be saved because there would be no remaining team with '
                        'the permission to change teams and permissions.'
                    )
                )

        return data
