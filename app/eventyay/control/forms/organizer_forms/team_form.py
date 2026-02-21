from collections import OrderedDict

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from django_scopes.forms import SafeModelMultipleChoiceField

from eventyay.base.models.organizer import Team
from eventyay.base.models.track import Track
from eventyay.control.forms.event import SafeEventMultipleChoiceField


class EventGroupedCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """A checkbox widget that adds data-event-id attributes to each choice
    for JavaScript-based event filtering."""

    def __init__(self, track_event_map=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Map of track_pk -> event_pk
        self.track_event_map = track_event_map or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value and str(value) in self.track_event_map:
            option['attrs']['data-event-id'] = self.track_event_map[str(value)]
        return option


class TeamForm(forms.ModelForm):
    @scopes_disabled()
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        self.organizer = organizer
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by('-has_subevents', '-date_from')
        tracks_qs = Track.objects.filter(
            event__organizer=organizer
        ).select_related('event').order_by("-event__date_from", "name")
        self.fields["limit_tracks"].queryset = tracks_qs

        # Build the track -> event mapping and update the widget
        track_event_map = {}
        for track in tracks_qs:
            track_event_map[str(track.pk)] = str(track.event_id)

        self.fields["limit_tracks"].widget = EventGroupedCheckboxSelectMultiple(
            track_event_map=track_event_map,
            attrs={
                'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
            },
        )

        # Build events with tracks for template context
        self._events_with_tracks = self._build_events_with_tracks(tracks_qs)

        # Cache selected track IDs now (inside scopes_disabled context)
        # so the template can use them without scope issues
        if self.instance and self.instance.pk:
            self._selected_track_ids = set(
                self.instance.limit_tracks.values_list('pk', flat=True)
            )
        else:
            self._selected_track_ids = set()

    def _build_events_with_tracks(self, tracks_qs):
        """Build an ordered dict of events with their tracks for template rendering."""
        events = OrderedDict()
        for track in tracks_qs:
            event = track.event
            if event.pk not in events:
                events[event.pk] = {
                    'id': event.pk,
                    'name': str(event.name),
                    'slug': event.slug,
                    'tracks': [],
                }
            events[event.pk]['tracks'].append({
                'id': track.pk,
                'name': str(track.name),
            })
        return list(events.values())

    @property
    def events_with_tracks(self):
        """Return events with their tracks for use in templates."""
        return self._events_with_tracks

    @property
    def selected_track_ids(self):
        """Return a set of currently selected track PKs for pre-checking checkboxes."""
        if self.is_bound:
            # Form was submitted — get from POST data
            field_name = self.add_prefix('limit_tracks')
            values = self.data.getlist(field_name)
            try:
                return {int(v) for v in values}
            except (ValueError, TypeError):
                return set()
        # On GET (page load) — return cached DB values
        return self._selected_track_ids

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
            'can_checkin_orders',
            'can_view_vouchers',
            'can_change_vouchers',
            'can_change_submissions',
            'is_reviewer',
            'force_hide_speaker_names',
            'limit_tracks',
            'can_video_create_stages',
            'can_video_create_channels',
            'can_video_direct_message',
            'can_video_manage_announcements',
            'can_video_view_users',
            'can_video_manage_users',
            'can_video_manage_rooms',
            'can_video_manage_kiosks',
            'can_video_manage_configuration',
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
                    'data-inverse-dependency': '#id_all_tracks',
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
        all_events = data.get("all_events")
        limit_events = data.get("limit_events")
        if not all_events and not limit_events:
            error = forms.ValidationError(
                _(
                    "Please either pick some events for this team, or grant access to all your events!"
                )
            )
            self.add_error("limit_events", error)

        permissions = (
            'can_create_events',
            'can_change_teams',
            'can_change_organizer_settings',
            'can_manage_gift_cards',
            'can_change_event_settings',
            'can_change_items',
            'can_view_orders',
            'can_change_orders',
            'can_checkin_orders',
            'can_view_vouchers',
            'can_change_vouchers',
            'can_change_submissions',
            'is_reviewer',
            'can_video_create_stages',
            'can_video_create_channels',
            'can_video_direct_message',
            'can_video_manage_announcements',
            'can_video_view_users',
            'can_video_manage_users',
            'can_video_manage_rooms',
            'can_video_manage_kiosks',
            'can_video_manage_configuration',
        )
        if not any(data.get(permission) for permission in permissions):
            error = forms.ValidationError(
                _("Please pick at least one permission for this team!")
            )
            self.add_error(None, error)
        
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
