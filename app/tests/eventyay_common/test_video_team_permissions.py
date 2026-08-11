import pytest
from django.core.cache import cache
from django.test import override_settings

from eventyay.base.models import Team
from eventyay.base.models import event as event_models
from eventyay.base.models import world as world_models
from eventyay.base.models.auth import User
from eventyay.base.services.user import (
    _ACCOUNT_HASH_MISS_TTL,
    _EMAIL_HASH_CACHE_MISS,
    _account_hash_cache_key,
    _add_hash_cache_misses,
    _cache_account_hash_hits,
    get_user,
    invalidate_account_hash_cache_for_emails,
    refresh_account_hash_cache,
)
from eventyay.core.permissions import (
    LEGACY_VIDEO_ROLE_NAMES,
    LEGACY_VIDEO_ROLE_PERMISSIONS,
    ORGANIZER_ROLES,
    SYSTEM_ROLES,
    VIDEO_ROLE_PERMISSIONS,
    Permission,
    default_roles,
)
from eventyay.eventyay_common.utils import encode_email
from eventyay.eventyay_common.video.permissions import (
    LEGACY_VIDEO_TRAIT_NAMES,
    VIDEO_PERMISSION_DEFINITIONS,
    collect_user_video_traits,
    managed_video_trait_values,
    replace_managed_video_traits,
)
from eventyay.eventyay_common.video.traits_sync import (
    apply_live_team_video_traits,
    sync_video_traits_for_platform_users,
)


@pytest.mark.django_db
def test_collect_user_video_traits_uses_consolidated_fields(event):
    traits = collect_user_video_traits(
        event.slug,
        {
            'can_video_manage_content',
            'can_video_moderate',
            'can_video_view_analytics',
            'can_change_config',
        },
    )
    assert set(traits) == {
        f'eventyay-video-event-{event.slug}-video-content-manager',
        f'eventyay-video-event-{event.slug}-video-moderator',
        f'eventyay-video-event-{event.slug}-video-analyst',
        f'eventyay-video-event-{event.slug}-video-config-manager',
    }


@pytest.mark.django_db
def test_content_manager_trait_grants_exhibition_and_poster(event):
    trait = f'eventyay-video-event-{event.slug}-video-content-manager'
    assert event.has_permission_implicit(
        traits=[trait],
        permissions=[
            Permission.EVENT_ROOMS_CREATE_EXHIBITION,
            Permission.EVENT_ROOMS_CREATE_POSTER,
            Permission.ROOM_UPDATE,
        ],
    )


@pytest.mark.django_db
def test_moderator_trait_covers_former_dashboard_gaps(event):
    trait = f'eventyay-video-event-{event.slug}-video-moderator'
    assert event.has_permission_implicit(
        traits=[trait],
        permissions=[
            Permission.ROOM_ANNOUNCE,
            Permission.ROOM_VIEWERS,
            Permission.ROOM_BBB_RECORDINGS,
            Permission.EVENT_ANNOUNCE,
            Permission.EVENT_USERS_LIST,
        ],
    )


@pytest.mark.django_db
def test_analytics_does_not_imply_configuration(event):
    analyst = f'eventyay-video-event-{event.slug}-video-analyst'
    config = f'eventyay-video-event-{event.slug}-video-config-manager'
    assert event.has_permission_implicit(
        traits=[analyst],
        permissions=[Permission.EVENT_GRAPHS],
    )
    assert not event.has_permission_implicit(
        traits=[analyst],
        permissions=[Permission.EVENT_UPDATE],
    )
    assert event.has_permission_implicit(
        traits=[config],
        permissions=[Permission.EVENT_UPDATE],
    )
    assert not event.has_permission_implicit(
        traits=[config],
        permissions=[Permission.EVENT_GRAPHS],
    )


def test_video_permission_definitions_match_option_a():
    assert set(VIDEO_PERMISSION_DEFINITIONS) == {
        'can_video_manage_content',
        'can_video_moderate',
        'can_video_manage_kiosks',
        'can_video_view_analytics',
        'can_change_config',
    }


@pytest.mark.django_db
def test_team_model_exposes_only_consolidated_video_fields(organizer):
    team = Team.objects.create(
        organizer=organizer,
        name='Video ops',
        can_video_manage_content=True,
        can_video_moderate=True,
        can_change_config=True,
    )
    perms = team.permission_set()
    assert 'can_video_manage_content' in perms
    assert 'can_video_moderate' in perms
    assert 'can_change_config' in perms
    assert 'can_video_create_stages' not in perms
    assert 'can_video_manage_users' not in perms
    assert 'can_video_manage_configuration' not in perms


@pytest.mark.django_db
def test_replace_managed_video_traits_keeps_attendee_and_admin(event):
    content = f'eventyay-video-event-{event.slug}-video-content-manager'
    legacy = f'eventyay-video-event-{event.slug}-video-stage-manager'
    result = replace_managed_video_traits(
        event.slug,
        ['attendee', content, legacy, 'admin'],
        [f'eventyay-video-event-{event.slug}-video-moderator'],
    )
    assert result == [
        'attendee',
        'admin',
        f'eventyay-video-event-{event.slug}-video-moderator',
    ]
    assert content in managed_video_trait_values(event.slug)
    assert legacy in managed_video_trait_values(event.slug)


@pytest.mark.django_db
def test_cached_jwt_traits_are_refreshed_from_live_team_grants(event, organizer, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Video ops',
        all_events=True,
        can_video_manage_content=True,
    )
    team.members.add(user)
    token_id = encode_email(user.email)
    stale_traits = [
        'attendee',
        f'eventyay-video-event-{event.slug}-video-content-manager',
        f'eventyay-video-event-{event.slug}-video-moderator',
    ]

    refreshed = apply_live_team_video_traits(event, token_id, stale_traits)
    assert f'eventyay-video-event-{event.slug}-video-content-manager' in refreshed
    assert f'eventyay-video-event-{event.slug}-video-moderator' not in refreshed

    team.can_video_manage_content = False
    team.save(update_fields=['can_video_manage_content'])
    user._teamcache = {}

    refreshed = apply_live_team_video_traits(event, token_id, stale_traits)
    assert f'eventyay-video-event-{event.slug}-video-content-manager' not in refreshed
    assert 'attendee' in refreshed


@pytest.mark.django_db
def test_get_user_ignores_revoked_team_traits_in_jwt(event, organizer, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Video ops',
        all_events=True,
        can_video_manage_content=False,
    )
    team.members.add(user)
    token_id = encode_email(user.email)
    content = f'eventyay-video-event-{event.slug}-video-content-manager'
    video_user = User.objects.create(
        event=event,
        token_id=token_id,
        traits=['attendee', content],
        profile={},
    )

    loaded = get_user(
        event=event,
        with_token={
            'uid': token_id,
            'traits': ['attendee', content],
        },
    )
    assert loaded.id == video_user.id
    assert content not in (loaded.traits or [])
    assert not event.has_permission(
        user=loaded,
        permission=Permission.EVENT_ROOMS_CREATE_STAGE,
    )


@pytest.mark.django_db
def test_sync_strips_revoked_traits_from_existing_video_user(event, organizer, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Video ops',
        all_events=True,
        can_video_manage_content=False,
    )
    team.members.add(user)
    token_id = encode_email(user.email)
    content = f'eventyay-video-event-{event.slug}-video-content-manager'
    video_user = User.objects.create(
        event=event,
        token_id=token_id,
        traits=['attendee', content],
        profile={},
    )

    sync_video_traits_for_platform_users(organizer, [user], force_reload=False)
    video_user.refresh_from_db()
    assert content not in (video_user.traits or [])
    assert 'attendee' in (video_user.traits or [])


@pytest.mark.django_db
def test_sync_matches_video_user_token_id_case_insensitively(event, organizer, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Video ops',
        all_events=True,
        can_video_manage_content=False,
    )
    team.members.add(user)
    token_id = encode_email(user.email)
    content = f'eventyay-video-event-{event.slug}-video-content-manager'
    video_user = User.objects.create(
        event=event,
        token_id=token_id.lower(),
        traits=['attendee', content],
        profile={},
    )

    sync_video_traits_for_platform_users(organizer, [user], force_reload=False)
    video_user.refresh_from_db()
    assert content not in (video_user.traits or [])
    assert 'attendee' in (video_user.traits or [])


@pytest.mark.django_db
def test_admin_trait_falls_back_when_roles_json_omits_admin(event):
    """Staff admin trait must not lose core perms if stored roles lack ``admin``."""
    # Partial roles JSON: video roles only (no admin key). SYSTEM_ROLES also has no admin.
    event.roles = {
        'video_content_manager': [
            Permission.EVENT_ROOMS_CREATE_STAGE.value,
            Permission.ROOM_UPDATE.value,
        ],
        'video_kiosk_manager': [Permission.EVENT_KIOSKS_MANAGE.value],
    }
    event.save(update_fields=['roles'])

    assert event.has_permission_implicit(
        traits=['admin'],
        permissions=[
            Permission.EVENT_UPDATE,
            Permission.EVENT_USERS_MANAGE,
            Permission.EVENT_ROOMS_CREATE_STAGE,
            Permission.EVENT_KIOSKS_MANAGE,
            Permission.EVENT_CONNECTIONS_UNLIMITED,
            Permission.ROOM_BBB_MODERATE,
            Permission.ROOM_INVITE,
        ],
    )


@pytest.mark.django_db
def test_admin_role_includes_kiosks_and_invite(event):
    assert event.has_permission_implicit(
        traits=['admin'],
        permissions=[Permission.EVENT_KIOSKS_MANAGE, Permission.ROOM_INVITE],
    )


def test_default_roles_are_shared_between_event_and_world():
    assert event_models.default_roles is default_roles
    assert world_models.default_roles is default_roles
    assert event_models.default_grants is world_models.default_grants
    roles = default_roles()
    assert set(VIDEO_ROLE_PERMISSIONS).issubset(roles)
    assert roles['video_content_manager'] == list(
        VIDEO_ROLE_PERMISSIONS['video_content_manager']
    )


def test_system_and_organizer_roles_derive_from_video_maps():
    for name, perms in VIDEO_ROLE_PERMISSIONS.items():
        assert SYSTEM_ROLES[name] == list(perms)
        assert name in ORGANIZER_ROLES
    for name, perms in LEGACY_VIDEO_ROLE_PERMISSIONS.items():
        assert SYSTEM_ROLES[name] == list(perms)
        assert name in ORGANIZER_ROLES
    assert LEGACY_VIDEO_TRAIT_NAMES == LEGACY_VIDEO_ROLE_NAMES
    assert set(LEGACY_VIDEO_ROLE_NAMES) == set(LEGACY_VIDEO_ROLE_PERMISSIONS)


_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'video-account-hash-tests',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
def test_invalidate_account_hash_cache_for_emails_clears_hits_and_misses():
    email = 'cache-person@example.com'
    token = encode_email(email)
    _cache_account_hash_hits(email, 'WikiPerson')
    assert cache.get(_account_hash_cache_key(token))['email'] == email

    cache.set(_account_hash_cache_key(token), _EMAIL_HASH_CACHE_MISS, 60)
    invalidate_account_hash_cache_for_emails([email])
    assert cache.get(_account_hash_cache_key(token)) is None


@override_settings(CACHES=_LOCMEM_CACHE)
def test_account_hash_miss_add_does_not_clobber_hit():
    email = 'race-person@example.com'
    token = encode_email(email)
    key = _account_hash_cache_key(token)
    _cache_account_hash_hits(email, 'WikiRace')
    _add_hash_cache_misses([key], ttl=_ACCOUNT_HASH_MISS_TTL)
    assert cache.get(key)['email'] == email


@override_settings(CACHES=_LOCMEM_CACHE)
def test_refresh_account_hash_cache_write_through_replaces_miss():
    email = 'refresh-person@example.com'
    token = encode_email(email)
    key = _account_hash_cache_key(token)
    cache.set(key, _EMAIL_HASH_CACHE_MISS, 60)
    refresh_account_hash_cache(email, 'WikiFresh')
    assert cache.get(key) == {
        'email': email,
        'wikimedia_username': 'WikiFresh',
    }


@pytest.mark.django_db
@override_settings(CACHES=_LOCMEM_CACHE)
def test_platform_user_save_invalidates_account_hash_cache(user):
    email = (user.email or '').strip()
    assert email
    assert user.event_id is None
    token = encode_email(email)
    key = _account_hash_cache_key(token)
    cache.set(key, _EMAIL_HASH_CACHE_MISS, 60)

    user.wikimedia_username = 'NewWiki'
    user.save(update_fields=['wikimedia_username'])
    assert cache.get(key) == {
        'email': email,
        'wikimedia_username': 'NewWiki',
    }

    user.save(update_fields=['last_login'])
    # Unrelated field updates must not drop the refreshed cache.
    assert cache.get(key)['wikimedia_username'] == 'NewWiki'
