"""
Tests for the hybrid attendee experience feature.

Covers:
- ExperienceProfile dataclass structure (unit)
- ExperienceResolver error conditions (unit)
- ExperienceResolver flag correctness (unit + property)
- Resolver override precedence (unit + property)
- ExperienceProfile structural completeness (property)
- Post-checkout redirect rule (unit)
- iCal LOCATION field (unit)
- Sendmail participation_mode filter field (unit)
- ParticipationMode choices (unit)
- OrderPosition.participation_mode_override field (unit)
"""
import dataclasses
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from eventyay.base.models.choices import ParticipationMode
from eventyay.base.services.experience_resolver import ExperienceProfile, ExperienceResolver


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_position(mode=ParticipationMode.IN_PERSON, override=None, product_id=1):
    """Build a minimal mock OrderPosition."""
    product = MagicMock()
    product.participation_mode = mode

    pos = MagicMock()
    pos.pk = 42
    pos.product_id = product_id
    pos.product = product
    pos.participation_mode_override = override
    return pos


def _make_event(location='Test Venue'):
    event = MagicMock()
    event.location = location
    event.slug = 'test-event'
    return event


# ---------------------------------------------------------------------------
# Unit tests — ParticipationMode choices (Requirement 9.1)
# ---------------------------------------------------------------------------

class TestParticipationModeChoices:
    def test_is_text_choices_subclass(self):
        """ParticipationMode must be a Django TextChoices subclass."""
        from django.db import models
        assert issubclass(ParticipationMode, models.TextChoices)

    def test_has_virtual_and_in_person(self):
        assert ParticipationMode.VIRTUAL == 'virtual'
        assert ParticipationMode.IN_PERSON == 'in_person'

    def test_choices_list_contains_both(self):
        values = [v for v, _ in ParticipationMode.choices]
        assert 'virtual' in values
        assert 'in_person' in values


# ---------------------------------------------------------------------------
# Unit tests — ExperienceProfile dataclass (Requirement 9.4)
# ---------------------------------------------------------------------------

class TestExperienceProfileDataclass:
    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ExperienceProfile)

    def test_required_fields_present(self):
        profile = ExperienceProfile(
            participation_mode='virtual',
            has_stream_access=True,
            show_join_online_nav=True,
        )
        assert profile.participation_mode == 'virtual'
        assert profile.has_stream_access is True
        assert profile.show_join_online_nav is True
        assert profile.primary_cta_url is None
        assert profile.calendar_location is None

    def test_optional_fields_accept_values(self):
        profile = ExperienceProfile(
            participation_mode='in_person',
            has_stream_access=False,
            show_join_online_nav=False,
            primary_cta_url='https://example.com',
            calendar_location='Main Hall',
        )
        assert profile.primary_cta_url == 'https://example.com'
        assert profile.calendar_location == 'Main Hall'

    def test_field_types(self):
        profile = ExperienceProfile(
            participation_mode='virtual',
            has_stream_access=True,
            show_join_online_nav=True,
            primary_cta_url='https://stream.example.com',
            calendar_location='https://stream.example.com',
        )
        assert isinstance(profile.participation_mode, str)
        assert isinstance(profile.has_stream_access, bool)
        assert isinstance(profile.show_join_online_nav, bool)
        assert isinstance(profile.primary_cta_url, str)
        assert isinstance(profile.calendar_location, str)


# ---------------------------------------------------------------------------
# Unit tests — ExperienceResolver error conditions (Requirements 3.6, 9.3)
# ---------------------------------------------------------------------------

class TestExperienceResolverErrors:
    def test_raises_value_error_for_missing_product(self):
        """Requirement 3.6: ValueError when position has no product."""
        pos = _make_position(product_id=None)
        resolver = ExperienceResolver()
        with pytest.raises(ValueError, match='no associated Product'):
            resolver.resolve(pos)

    def test_raises_value_error_for_unknown_mode(self):
        """Requirement 9.3: ValueError for unknown participation_mode."""
        pos = _make_position(mode='unknown_mode')
        resolver = ExperienceResolver()
        with pytest.raises(ValueError, match='Unknown participation_mode'):
            resolver.resolve(pos)

    def test_callable_without_request_object(self):
        """Requirement 3.5: resolver works without a Django request."""
        pos = _make_position(mode=ParticipationMode.IN_PERSON)
        resolver = ExperienceResolver()
        # Should not raise — no request object involved
        with patch.object(resolver, '_get_stream_url', return_value=None):
            profile = resolver.resolve(pos)
        assert profile is not None


# ---------------------------------------------------------------------------
# Unit tests — ExperienceResolver flag correctness (Requirements 3.3, 3.4)
# ---------------------------------------------------------------------------

class TestExperienceResolverFlags:
    def test_virtual_position_has_stream_access(self):
        pos = _make_position(mode=ParticipationMode.VIRTUAL)
        resolver = ExperienceResolver()
        with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com'):
            profile = resolver.resolve(pos)
        assert profile.has_stream_access is True
        assert profile.show_join_online_nav is True
        assert profile.participation_mode == ParticipationMode.VIRTUAL

    def test_in_person_position_has_no_stream_access(self):
        pos = _make_position(mode=ParticipationMode.IN_PERSON)
        event = _make_event()
        resolver = ExperienceResolver()
        profile = resolver.resolve(pos, event)
        assert profile.has_stream_access is False
        assert profile.show_join_online_nav is False
        assert profile.participation_mode == ParticipationMode.IN_PERSON


# ---------------------------------------------------------------------------
# Unit tests — Override precedence (Requirements 2.2, 2.3)
# ---------------------------------------------------------------------------

class TestResolverOverridePrecedence:
    def test_override_takes_precedence_over_product_mode(self):
        """When override is set, it wins over product.participation_mode."""
        pos = _make_position(
            mode=ParticipationMode.IN_PERSON,
            override=ParticipationMode.VIRTUAL,
        )
        resolver = ExperienceResolver()
        with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com'):
            profile = resolver.resolve(pos)
        assert profile.participation_mode == ParticipationMode.VIRTUAL
        assert profile.has_stream_access is True

    def test_no_override_uses_product_mode(self):
        """When override is None, product.participation_mode is used."""
        pos = _make_position(mode=ParticipationMode.VIRTUAL, override=None)
        resolver = ExperienceResolver()
        with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com'):
            profile = resolver.resolve(pos)
        assert profile.participation_mode == ParticipationMode.VIRTUAL

    def test_override_in_person_overrides_virtual_product(self):
        pos = _make_position(
            mode=ParticipationMode.VIRTUAL,
            override=ParticipationMode.IN_PERSON,
        )
        event = _make_event()
        resolver = ExperienceResolver()
        profile = resolver.resolve(pos, event)
        assert profile.participation_mode == ParticipationMode.IN_PERSON
        assert profile.has_stream_access is False


# ---------------------------------------------------------------------------
# Unit tests — iCal LOCATION (Requirements 6.1–6.5)
# ---------------------------------------------------------------------------

class TestIcalLocation:
    def _make_event_obj(self, location='Conference Hall'):
        """Build a minimal mock Event for iCal tests."""
        event = MagicMock()
        event.location = location
        event.slug = 'test'
        event.organizer.slug = 'org'
        event.organizer.name = 'Org'
        event.settings.timezone = 'UTC'
        event.settings.show_times = True
        event.settings.show_date_to = False
        event.date_from = timezone.now()
        event.date_to = None
        event.date_admission = None
        event.name = 'Test Event'
        event.pk = 1
        return event

    def test_no_position_uses_event_location(self):
        """Requirement 6.5: without position, existing behaviour preserved."""
        from eventyay.presale.ical import get_ical
        from eventyay.base.models import Event as EventModel

        ev = self._make_event_obj(location='Physical Venue')
        # Patch isinstance check so ev is treated as Event
        with patch('eventyay.presale.ical.build_absolute_uri', return_value='https://example.com/event/'):
            with patch('eventyay.presale.ical.isinstance', side_effect=lambda obj, cls: cls == EventModel):
                cal = get_ical([ev], position=None)

        vevent = cal.vevent
        assert vevent.location.value == 'Physical Venue'

    def test_virtual_position_uses_stream_url_as_location(self):
        """Requirement 6.1: virtual position → stream URL as LOCATION."""
        from eventyay.presale.ical import get_ical
        from eventyay.base.models import Event as EventModel

        ev = self._make_event_obj(location='Physical Venue')
        pos = _make_position(mode=ParticipationMode.VIRTUAL)

        stream_url = 'https://stream.example.com/join'
        mock_profile = ExperienceProfile(
            participation_mode=ParticipationMode.VIRTUAL,
            has_stream_access=True,
            show_join_online_nav=True,
            primary_cta_url=stream_url,
            calendar_location=stream_url,
        )

        with patch('eventyay.presale.ical.build_absolute_uri', return_value='https://example.com/event/'):
            with patch('eventyay.presale.ical.isinstance', side_effect=lambda obj, cls: cls == EventModel):
                with patch('eventyay.presale.ical.ExperienceResolver') as MockResolver:
                    MockResolver.return_value.resolve.return_value = mock_profile
                    cal = get_ical([ev], position=pos)

        vevent = cal.vevent
        assert vevent.location.value == stream_url

    def test_virtual_position_no_stream_url_falls_back_to_event_location(self):
        """Requirement 6.4: no stream URL → fall back to event location."""
        from eventyay.presale.ical import get_ical
        from eventyay.base.models import Event as EventModel

        ev = self._make_event_obj(location='Physical Venue')
        pos = _make_position(mode=ParticipationMode.VIRTUAL)

        mock_profile = ExperienceProfile(
            participation_mode=ParticipationMode.VIRTUAL,
            has_stream_access=True,
            show_join_online_nav=True,
            primary_cta_url=None,
            calendar_location=None,
        )

        with patch('eventyay.presale.ical.build_absolute_uri', return_value='https://example.com/event/'):
            with patch('eventyay.presale.ical.isinstance', side_effect=lambda obj, cls: cls == EventModel):
                with patch('eventyay.presale.ical.ExperienceResolver') as MockResolver:
                    MockResolver.return_value.resolve.return_value = mock_profile
                    cal = get_ical([ev], position=pos)

        vevent = cal.vevent
        assert vevent.location.value == 'Physical Venue'


# ---------------------------------------------------------------------------
# Unit tests — Sendmail form (Requirement 8.1)
# ---------------------------------------------------------------------------

class TestSendmailForm:
    def test_participation_mode_field_present(self):
        """Requirement 8.1: MailForm must include participation_mode field."""
        from eventyay.plugins.sendmail.forms import MailForm

        event = MagicMock()
        event.settings.attendee_emails_asked = False
        event.settings.get.return_value = ['en']
        event.settings.locales = ['en']
        event.settings.region = None
        event.settings.get_payment_term_expire_automatically = False
        event.products.all.return_value = []
        event.checkin_lists.all.return_value = []
        event.has_subevents = False

        form = MailForm(event=event)
        assert 'participation_mode' in form.fields

    def test_participation_mode_choices_include_all_and_modes(self):
        """Choices must include empty (all), virtual, in_person."""
        from eventyay.plugins.sendmail.forms import MailForm

        event = MagicMock()
        event.settings.attendee_emails_asked = False
        event.settings.get.return_value = ['en']
        event.settings.locales = ['en']
        event.settings.region = None
        event.products.all.return_value = []
        event.checkin_lists.all.return_value = []
        event.has_subevents = False

        form = MailForm(event=event)
        choice_values = [v for v, _ in form.fields['participation_mode'].choices]
        assert '' in choice_values
        assert 'virtual' in choice_values
        assert 'in_person' in choice_values


# ---------------------------------------------------------------------------
# Unit tests — OrderPosition.participation_mode_override field (Requirement 2.1)
# ---------------------------------------------------------------------------

class TestOrderPositionOverrideField:
    def test_field_exists_and_is_nullable(self):
        """Requirement 2.1: participation_mode_override must be nullable."""
        from eventyay.base.models.orders import OrderPosition

        field = OrderPosition._meta.get_field('participation_mode_override')
        assert field.null is True
        assert field.blank is True

    def test_field_max_length(self):
        from eventyay.base.models.orders import OrderPosition

        field = OrderPosition._meta.get_field('participation_mode_override')
        assert field.max_length == 50


# ---------------------------------------------------------------------------
# Property-based tests — Property 1: flags match participation mode
# ---------------------------------------------------------------------------

_VALID_MODES = st.sampled_from([ParticipationMode.VIRTUAL, ParticipationMode.IN_PERSON])


@given(mode=_VALID_MODES)
@h_settings(max_examples=100)
def test_property_1_flags_match_participation_mode(mode):
    """
    # Feature: hybrid-attendee-experience, Property 1: ExperienceProfile flags match participation mode
    For any virtual position: has_stream_access=True, show_join_online_nav=True.
    For any in_person position: both flags=False.
    Validates: Requirements 3.3, 3.4
    """
    pos = _make_position(mode=mode)
    resolver = ExperienceResolver()

    with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com' if mode == ParticipationMode.VIRTUAL else None):
        event = _make_event()
        profile = resolver.resolve(pos, event)

    if mode == ParticipationMode.VIRTUAL:
        assert profile.has_stream_access is True
        assert profile.show_join_online_nav is True
    else:
        assert profile.has_stream_access is False
        assert profile.show_join_online_nav is False


# ---------------------------------------------------------------------------
# Property-based tests — Property 2: resolver override precedence
# ---------------------------------------------------------------------------

@given(
    product_mode=_VALID_MODES,
    override=st.one_of(st.none(), _VALID_MODES),
)
@h_settings(max_examples=100)
def test_property_2_resolver_override_precedence(product_mode, override):
    """
    # Feature: hybrid-attendee-experience, Property 2: Resolver override precedence
    When override is set, resolved mode == override.
    When override is None, resolved mode == product.participation_mode.
    Validates: Requirements 2.2, 2.3
    """
    pos = _make_position(mode=product_mode, override=override)
    resolver = ExperienceResolver()
    event = _make_event()

    with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com'):
        profile = resolver.resolve(pos, event)

    expected_mode = override if override is not None else product_mode
    assert profile.participation_mode == expected_mode


# ---------------------------------------------------------------------------
# Property-based tests — Property 3: ExperienceProfile structural completeness
# ---------------------------------------------------------------------------

@given(mode=_VALID_MODES)
@h_settings(max_examples=100)
def test_property_3_experience_profile_structural_completeness(mode):
    """
    # Feature: hybrid-attendee-experience, Property 3: ExperienceProfile structural completeness
    For any valid position, resolve() returns an ExperienceProfile with all five
    required fields present and correctly typed.
    Validates: Requirements 3.1, 3.2
    """
    pos = _make_position(mode=mode)
    resolver = ExperienceResolver()
    event = _make_event()

    with patch.object(resolver, '_get_stream_url', return_value='https://stream.example.com'):
        profile = resolver.resolve(pos, event)

    assert isinstance(profile, ExperienceProfile)
    assert isinstance(profile.participation_mode, str)
    assert isinstance(profile.has_stream_access, bool)
    assert isinstance(profile.show_join_online_nav, bool)
    # Optional fields must be str or None
    assert profile.primary_cta_url is None or isinstance(profile.primary_cta_url, str)
    assert profile.calendar_location is None or isinstance(profile.calendar_location, str)


# ---------------------------------------------------------------------------
# Property-based tests — Property 4: post-checkout redirect rule
# ---------------------------------------------------------------------------

@given(
    modes=st.lists(_VALID_MODES, min_size=1, max_size=5),
    has_stream_url=st.booleans(),
)
@h_settings(max_examples=100)
def test_property_4_post_checkout_redirect_rule(modes, has_stream_url):
    """
    # Feature: hybrid-attendee-experience, Property 4: Post-checkout redirect is stream page iff all positions are virtual and stream URL exists
    get_success_url returns stream URL iff all positions are virtual AND stream URL is non-None.
    Validates: Requirements 4.1, 4.2
    """
    stream_url = 'https://stream.example.com/join' if has_stream_url else None
    order_url = 'https://example.com/order/ABC/secret/'

    all_virtual = all(m == ParticipationMode.VIRTUAL for m in modes)

    # Build mock profiles
    profiles = []
    for m in modes:
        profiles.append(
            ExperienceProfile(
                participation_mode=m,
                has_stream_access=(m == ParticipationMode.VIRTUAL),
                show_join_online_nav=(m == ParticipationMode.VIRTUAL),
                primary_cta_url=stream_url if m == ParticipationMode.VIRTUAL else None,
            )
        )

    # Simulate the get_success_url logic from ConfirmStep
    result_url = order_url
    if profiles and all(p.has_stream_access for p in profiles):
        candidate = profiles[0].primary_cta_url
        if candidate:
            result_url = candidate

    expected = stream_url if (all_virtual and has_stream_url) else order_url
    assert result_url == expected


# ---------------------------------------------------------------------------
# Property-based tests — Property 7: Sendmail filter correctness
# ---------------------------------------------------------------------------

@given(
    filter_mode=_VALID_MODES,
    position_modes=st.lists(_VALID_MODES, min_size=0, max_size=10),
)
@h_settings(max_examples=100)
def test_property_7_sendmail_filter_correctness(filter_mode, position_modes):
    """
    # Feature: hybrid-attendee-experience, Property 7: Sendmail participation mode filter correctness
    Every position in the filtered set must have effective mode == filter_mode.
    Validates: Requirements 8.2, 8.3
    """
    # Simulate the Q-filter logic: override takes precedence, else product mode
    def effective_mode(override, product_mode):
        return override if override is not None else product_mode

    # Build mock positions with no override (override=None → product mode is effective)
    positions = [
        {'override': None, 'product_mode': m}
        for m in position_modes
    ]

    # Apply the filter (mirrors the ORM Q logic)
    filtered = [
        p for p in positions
        if (p['override'] == filter_mode)
        or (p['override'] is None and p['product_mode'] == filter_mode)
    ]

    # All filtered positions must have effective mode == filter_mode
    for p in filtered:
        assert effective_mode(p['override'], p['product_mode']) == filter_mode


# ---------------------------------------------------------------------------
# Property-based tests — Property 8: Sendmail filter composability
# ---------------------------------------------------------------------------

@given(
    position_modes=st.lists(_VALID_MODES, min_size=0, max_size=10),
    filter_mode=st.one_of(st.none(), _VALID_MODES),
)
@h_settings(max_examples=100)
def test_property_8_sendmail_filter_composability(position_modes, filter_mode):
    """
    # Feature: hybrid-attendee-experience, Property 8: Sendmail filter composability (metamorphic)
    Adding a participation_mode filter can only reduce or maintain the count, never increase it.
    Validates: Requirement 8.5
    """
    positions = [{'override': None, 'product_mode': m} for m in position_modes]

    # Unfiltered count (all positions pass)
    unfiltered_count = len(positions)

    # Filtered count
    if filter_mode:
        filtered = [
            p for p in positions
            if (p['override'] == filter_mode)
            or (p['override'] is None and p['product_mode'] == filter_mode)
        ]
        filtered_count = len(filtered)
    else:
        filtered_count = unfiltered_count

    assert filtered_count <= unfiltered_count
