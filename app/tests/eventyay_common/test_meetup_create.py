from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from PIL import Image


@receiver(connection_created)
def _enable_pg_trgm(sender, connection, **kwargs):
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')

from eventyay.base.meetup import (
    get_rsvp_product_and_quota,
    has_video_stream,
    is_meetup_event,
)
from eventyay.base.models import Event, EventHeaderPreset, EventHeaderPresetCategory, Team, User
from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def orga_client(client, organizer):
    GlobalSettingsObject().settings.set('meetup_creation_enabled', True)
    user = User.objects.create_superuser('organizer_user@test.org', 'testpass123')
    team = Team.objects.create(
        organizer=organizer,
        all_events=True,
        can_create_events=True,
        can_change_teams=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_items=True,
        can_view_orders=True,
        can_change_orders=True,
        can_view_vouchers=True,
        can_change_vouchers=True,
    )
    team.members.add(user)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


def _create_test_image():
    out = BytesIO()
    im = Image.new('RGB', (800, 450), color=(73, 109, 137))
    im.save(out, format='PNG')
    out.seek(0)
    return SimpleUploadedFile('test_cover.png', out.read(), content_type='image/png')


def _create_test_preset(category_name=None, category_slug=None, name='Sunset Glow'):
    effective_name = category_name or (category_slug.title() if category_slug else 'Gradients')
    category, _ = EventHeaderPresetCategory.objects.get_or_create(
        name=effective_name,
    )
    preset = EventHeaderPreset.objects.create(
        name=name,
        category=category,
        image=_create_test_image(),
        thumbnail=_create_test_image(),
        is_active=True,
    )
    from eventyay.base.header_presets import invalidate_preset_cache
    invalidate_preset_cache()
    return preset


@pytest.mark.django_db
def test_meetup_create_get_renders_meetup_template(orga_client):
    url = reverse('eventyay_common:events.add') + '?meetup=1'
    response = orga_client.get(url)
    assert response.status_code == 200
    assert 'eventyay_common/events/meetup_create.html' in [t.name for t in response.templates]


@pytest.mark.django_db
def test_standard_event_create_get_renders_standard_template(orga_client):
    url = reverse('eventyay_common:events.add')
    response = orga_client.get(url)
    assert response.status_code == 200
    assert 'eventyay_common/events/create.html' in [t.name for t in response.templates]


@pytest.mark.django_db
def test_meetup_create_post_success_in_person_unlimited(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'PyData Meetup',
        'basics-date_from_0': '2026-10-15',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-15',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Tech Hub Hall A',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='PyData Meetup').first()
        assert event is not None
        assert str(event.name) == 'PyData Meetup'
        assert is_meetup_event(event) is True
        assert event.live is True
        assert event.tickets_published is True
        assert bool(event.slug) is True  # Slug auto-generated

        product, quota = get_rsvp_product_and_quota(event)
        assert product is not None
        assert quota is not None
        assert quota.size is None


@pytest.mark.django_db
def test_meetup_create_post_with_description_and_capacity_limit(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'AI Builders Night',
        'basics-date_from_0': '2026-11-01',
        'basics-date_from_1': '19:00:00',
        'basics-date_to_0': '2026-11-01',
        'basics-date_to_1': '21:00:00',
        'basics-timezone': 'UTC',
        'basics-frontpage_text_0': 'Join us for talks on modern generative agents and tooling.',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Innovation Center',
        'basics-capacity_type': 'limited',
        'basics-registration_limit': 60,
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='AI Builders Night').first()
        assert event is not None
        assert str(event.name) == 'AI Builders Night'
        assert is_meetup_event(event) is True
        assert str(event.settings.frontpage_text) == 'Join us for talks on modern generative agents and tooling.'

        product, quota = get_rsvp_product_and_quota(event)
        assert quota is not None
        assert quota.size == 60


@pytest.mark.django_db
def test_meetup_create_post_virtual_with_video_stream(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Global Online Tech Talk',
        'basics-date_from_0': '2026-12-05',
        'basics-date_from_1': '17:00:00',
        'basics-date_to_0': '2026-12-05',
        'basics-date_to_1': '18:30:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'virtual',
        'basics-location_0': '123 Physical Street',
        'basics-geo_lat': '40.712800',
        'basics-geo_lon': '-74.006000',
        'basics-video_type': 'youtube',
        'basics-video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Global Online Tech Talk').first()
        assert event is not None
        assert str(event.name) == 'Global Online Tech Talk'
        assert is_meetup_event(event) is True
        assert has_video_stream(event) is True
        assert event.settings.meetup_video_active is True
        assert not event.location
        assert event.geo_lat is None
        assert event.geo_lon is None


@pytest.mark.django_db
def test_meetup_create_post_with_cover_image(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    test_image = _create_test_image()
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Design Systems Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Design Studio 4B',
        'basics-capacity_type': 'unlimited',
        'basics-logo_image': test_image,
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Design Systems Meetup').first()
        assert event is not None
        assert str(event.name) == 'Design Systems Meetup'
        assert is_meetup_event(event) is True
        header_img = event.settings.get('logo_image', as_type=str, default='')
        assert header_img.startswith('file://')
        assert bool(event.visible_header_image_url) is True


@pytest.mark.django_db
def test_meetup_create_validation_errors(orga_client, organizer):
    url = reverse('eventyay_common:events.add')

    # Video type provided but URL missing
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Invalid Virtual Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'virtual',
        'basics-video_type': 'youtube',
        'basics-video_url': '',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 200
    assert 'basics_form' in response.context
    assert 'video_url' in response.context['basics_form'].errors

    # Limited capacity missing registration limit
    data_limited = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Invalid Capacity Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Room 1',
        'basics-capacity_type': 'limited',
        'basics-registration_limit': '',
    }
    response_limited = orga_client.post(url, data_limited)
    assert response_limited.status_code == 200
    assert 'registration_limit' in response_limited.context['basics_form'].errors


@pytest.mark.django_db
def test_meetup_create_context_includes_header_presets(orga_client):
    preset = _create_test_preset(category_slug='gradients', name='Sunset Glow')
    url = reverse('eventyay_common:events.add') + '?meetup=1'
    response = orga_client.get(url)
    assert response.status_code == 200
    assert 'header_presets' in response.context
    assert len(response.context['header_presets']) > 0
    assert 'preset_categories' in response.context
    assert 'initial_preset_id' in response.context
    assert bool(response.context['initial_preset_id']) is True
    assert 'initial_preset_url' in response.context
    assert bool(response.context['initial_preset_url']) is True


@pytest.mark.django_db
def test_meetup_create_with_preset(orga_client, organizer):
    preset = _create_test_preset(category_slug='gradients', name='Sunset Glow')
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Preset Banner Meetup',
        'basics-date_from_0': '2026-11-15',
        'basics-date_from_1': '10:00:00',
        'basics-date_to_0': '2026-11-15',
        'basics-date_to_1': '12:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Innovation Lab',
        'basics-capacity_type': 'unlimited',
        'basics-header_image_preset': str(preset.pk),
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Preset Banner Meetup').first()
        assert event is not None
        assert is_meetup_event(event) is True
        assert event.settings.get('logo_image', as_type=str) == f'preset:{preset.pk}'
        assert event.visible_header_image_url is not None
        assert event.visible_header_image_file is not None
        assert event.preview_image_url_with_fallback is not None


@pytest.mark.django_db
def test_meetup_create_custom_image_overrides_preset(orga_client, organizer):
    preset = _create_test_preset(category_slug='abstract', name='Abstract Waves')
    url = reverse('eventyay_common:events.add')
    test_image = _create_test_image()
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Custom Upload Overrides Preset Meetup',
        'basics-date_from_0': '2026-11-20',
        'basics-date_from_1': '14:00:00',
        'basics-date_to_0': '2026-11-20',
        'basics-date_to_1': '16:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Studio 1',
        'basics-capacity_type': 'unlimited',
        'basics-header_image_preset': str(preset.pk),
        'basics-logo_image': test_image,
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Custom Upload Overrides Preset Meetup').first()
        assert event is not None
        logo_setting = event.settings.get('logo_image', as_type=str)
        assert logo_setting.startswith('file://')
        assert not logo_setting.startswith('preset:')
        assert event.visible_header_image_url is not None


@pytest.mark.django_db
def test_meetup_create_invalid_preset_rejected(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Invalid Preset Meetup',
        'basics-date_from_0': '2026-11-20',
        'basics-date_from_1': '14:00:00',
        'basics-date_to_0': '2026-11-20',
        'basics-date_to_1': '16:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Studio 1',
        'basics-capacity_type': 'unlimited',
        'basics-header_image_preset': '999999',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 200
    assert 'basics_form' in response.context
    assert 'header_image_preset' in response.context['basics_form'].errors


@pytest.mark.django_db
def test_preset_resolution_in_event_model(organizer):
    preset = _create_test_preset(category_slug='gradients', name='Ocean Breeze')
    with scopes_disabled():
        event = Event.objects.create(
            organizer=organizer,
            name='Direct Model Preset Test',
            slug='direct-model-preset-test',
            date_from=now(),
            date_to=now(),
        )
        event.settings.set('logo_image', f'preset:{preset.pk}')

        assert event._visible_header_image_path == f'preset:{preset.pk}'
        assert event.visible_header_image_url is not None
        assert event.visible_header_image_file is not None
        assert event.preview_image_url_with_fallback is not None
        assert event.preview_image_url_small is not None


@pytest.mark.django_db
def test_meetup_create_get_without_organizer_renders_warning_gracefully(client):
    GlobalSettingsObject().settings.set('meetup_creation_enabled', True)
    user = User.objects.create_user('no_orga_user@test.org', 'testpass123')
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)

    # Standard event creation handles missing organizer gracefully in template
    url = reverse('eventyay_common:events.add')
    response = client.get(url)
    assert response.status_code == 200
    assert response.context['has_organizer'] is False
    assert response.context['basics_form'] is None

    # Meetup creation without organizer permission raises PermissionDenied (403)
    meetup_url = reverse('eventyay_common:events.add') + '?meetup=1'
    meetup_response = client.get(meetup_url)
    assert meetup_response.status_code == 403


@pytest.mark.django_db
def test_meetup_create_preset_preserved_on_validation_error(orga_client, organizer):
    preset = _create_test_preset(category_slug='abstract', name='Abstract Waves')
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': '',  # missing name triggers validation error
        'basics-date_from_0': '2026-11-20',
        'basics-date_from_1': '14:00:00',
        'basics-date_to_0': '2026-11-20',
        'basics-date_to_1': '16:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Studio 1',
        'basics-capacity_type': 'unlimited',
        'basics-header_image_preset': str(preset.pk),
    }
    response = orga_client.post(url, data)
    assert response.status_code == 200
    assert 'basics_form' in response.context
    assert 'name' in response.context['basics_form'].errors
    assert response.context['initial_preset_id'] == str(preset.pk)
    assert response.context['initial_preset_url'] is not None


@pytest.mark.django_db
def test_meetup_create_with_no_presets_in_db(orga_client):
    from eventyay.base.header_presets import invalidate_preset_cache
    EventHeaderPreset.objects.all().delete()
    invalidate_preset_cache()

    url = reverse('eventyay_common:events.add') + '?meetup=1'
    response = orga_client.get(url)
    assert response.status_code == 200
    assert response.context['header_presets'] == []
    assert response.context['initial_preset_id'] == ''
    assert response.context['initial_preset_url'] == ''
