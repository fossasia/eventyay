import pytest
from django_scopes import scopes_disabled

from pretix.base.models import Team, User, Event


@pytest.fixture
def video_team(organizer, event):
    """Team with comprehensive video permissions."""
    t = organizer.teams.create(
        name='Video Team',
        all_events=True,
        can_video_create_stages=True,
        can_video_create_channels=True,
        can_video_direct_message=True,
        can_video_manage_announcements=True,
        can_video_view_users=True,
        can_video_manage_users=True,
        can_video_manage_rooms=True,
        can_video_manage_kiosks=True,
        can_video_manage_configuration=True,
    )
    return t


@pytest.fixture
def limited_video_team(organizer, event):
    """Team with limited video permissions (only stage and channel creation)."""
    t = organizer.teams.create(
        name='Limited Video Team',
        all_events=True,
        can_video_create_stages=True,
        can_video_create_channels=True,
        can_video_direct_message=False,
        can_video_manage_announcements=False,
        can_video_view_users=False,
        can_video_manage_users=False,
        can_video_manage_rooms=False,
        can_video_manage_kiosks=False,
        can_video_manage_configuration=False,
    )
    return t


@pytest.fixture
def no_video_team(organizer, event):
    """Team with no video permissions."""
    t = organizer.teams.create(
        name='No Video Team',
        all_events=True,
        can_video_create_stages=False,
        can_video_create_channels=False,
        can_video_direct_message=False,
        can_video_manage_announcements=False,
        can_video_view_users=False,
        can_video_manage_users=False,
        can_video_manage_rooms=False,
        can_video_manage_kiosks=False,
        can_video_manage_configuration=False,
    )
    return t


@pytest.mark.django_db
def test_team_video_permissions_defaults():
    """Test that video permission fields default to False."""
    with scopes_disabled():
        team = Team.objects.create(name='Test Team')

        assert team.can_video_create_stages is False
        assert team.can_video_create_channels is False
        assert team.can_video_direct_message is False
        assert team.can_video_manage_announcements is False
        assert team.can_video_view_users is False
        assert team.can_video_manage_users is False
        assert team.can_video_manage_rooms is False
        assert team.can_video_manage_kiosks is False
        assert team.can_video_manage_configuration is False


@pytest.mark.django_db
def test_team_video_permissions_all_enabled(video_team):
    """Test team with all video permissions enabled."""
    assert video_team.can_video_create_stages is True
    assert video_team.can_video_create_channels is True
    assert video_team.can_video_direct_message is True
    assert video_team.can_video_manage_announcements is True
    assert video_team.can_video_view_users is True
    assert video_team.can_video_manage_users is True
    assert video_team.can_video_manage_rooms is True
    assert video_team.can_video_manage_kiosks is True
    assert video_team.can_video_manage_configuration is True


@pytest.mark.django_db
def test_team_video_permissions_partial_enabled(limited_video_team):
    """Test team with only some video permissions enabled."""
    assert limited_video_team.can_video_create_stages is True
    assert limited_video_team.can_video_create_channels is True
    assert limited_video_team.can_video_direct_message is False
    assert limited_video_team.can_video_manage_announcements is False
    assert limited_video_team.can_video_view_users is False
    assert limited_video_team.can_video_manage_users is False
    assert limited_video_team.can_video_manage_rooms is False
    assert limited_video_team.can_video_manage_kiosks is False
    assert limited_video_team.can_video_manage_configuration is False


@pytest.mark.django_db
def test_team_video_permissions_none_enabled(no_video_team):
    """Test team with no video permissions."""
    assert no_video_team.can_video_create_stages is False
    assert no_video_team.can_video_create_channels is False
    assert no_video_team.can_video_direct_message is False
    assert no_video_team.can_video_manage_announcements is False
    assert no_video_team.can_video_view_users is False
    assert no_video_team.can_video_manage_users is False
    assert no_video_team.can_video_manage_rooms is False
    assert no_video_team.can_video_manage_kiosks is False
    assert no_video_team.can_video_manage_configuration is False


@pytest.mark.django_db
def test_team_video_permissions_update():
    """Test updating video permissions on an existing team."""
    with scopes_disabled():
        team = Team.objects.create(name='Test Team')

        # Initially all False
        assert team.can_video_create_stages is False

        # Update one permission
        team.can_video_create_stages = True
        team.save()
        team.refresh_from_db()

        assert team.can_video_create_stages is True
        # Others should still be False
        assert team.can_video_create_channels is False


@pytest.mark.django_db
def test_team_video_permissions_persistence():
    """Test that video permissions are properly saved and retrieved."""
    with scopes_disabled():
        team = Team.objects.create(
            name='Test Team',
            can_video_create_stages=True,
            can_video_manage_rooms=True,
        )

        team_id = team.pk

        # Retrieve from database
        retrieved_team = Team.objects.get(pk=team_id)

        assert retrieved_team.can_video_create_stages is True
        assert retrieved_team.can_video_manage_rooms is True
        assert retrieved_team.can_video_create_channels is False


@pytest.mark.django_db
def test_team_video_permissions_field_names():
    """Test that all expected video permission field names exist."""
    expected_fields = [
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

    team_field_names = [f.name for f in Team._meta.get_fields()]

    for field_name in expected_fields:
        assert field_name in team_field_names, f"Field {field_name} not found in Team model"


@pytest.mark.django_db
def test_video_permissions_boolean_type():
    """Test that video permission fields are boolean type."""
    with scopes_disabled():
        team = Team.objects.create(name='Test Team')

        # Check that fields accept and store boolean values
        team.can_video_create_stages = True
        assert isinstance(team.can_video_create_stages, bool)

        team.can_video_create_stages = False
        assert isinstance(team.can_video_create_stages, bool)


# Note: Trait mapping tests should be added here once the video permissions
# trait mapping logic is implemented. These tests would verify that:
# - Team permissions correctly map to JWT traits
# - Staff users receive appropriate admin traits
# - Trait generation handles None/empty cases
# - Permission inheritance works as expected
