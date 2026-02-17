import pytest
from django.core.files.base import ContentFile
from django_scopes import scopes_disabled

from pretix.testutils.mock import mocker_context

TEST_ORGANIZER_RES = {'name': 'Dummy', 'slug': 'dummy'}


@pytest.mark.django_db
def test_organizer_list(token_client, organizer):
    resp = token_client.get('/api/v1/organizers/')
    assert resp.status_code == 200
    assert TEST_ORGANIZER_RES in resp.data['results']


@pytest.mark.django_db
def test_organizer_detail(token_client, organizer):
    resp = token_client.get('/api/v1/organizers/{}/'.format(organizer.slug))
    assert resp.status_code == 200
    assert TEST_ORGANIZER_RES == resp.data


@pytest.mark.django_db
def test_get_settings(token_client, organizer):
    organizer.settings.event_list_type = 'week'
    resp = token_client.get(
        '/api/v1/organizers/{}/settings/'.format(
            organizer.slug,
        ),
    )
    assert resp.status_code == 200
    assert resp.data['event_list_type'] == 'week'

    resp = token_client.get(
        '/api/v1/organizers/{}/settings/?explain=true'.format(organizer.slug),
    )
    assert resp.status_code == 200
    assert resp.data['event_list_type'] == {
        'value': 'week',
        'label': 'Default overview style',
        'help_text': 'If your event series has more than 50 dates in the future, only the month or week calendar can be used.',
    }


@pytest.mark.django_db
def test_patch_settings(token_client, organizer):
    with mocker_context() as mocker:
        mocked = mocker.patch('pretix.presale.style.regenerate_organizer_css.apply_async')

        organizer.settings.event_list_type = 'week'
        resp = token_client.patch(
            '/api/v1/organizers/{}/settings/'.format(organizer.slug),
            {'event_list_type': 'list'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['event_list_type'] == 'list'
        organizer.settings.flush()
        assert organizer.settings.event_list_type == 'list'

        resp = token_client.patch(
            '/api/v1/organizers/{}/settings/'.format(organizer.slug),
            {
                'event_list_type': None,
            },
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['event_list_type'] == 'list'
        organizer.settings.flush()
        assert organizer.settings.event_list_type == 'list'
        mocked.assert_not_called()

        resp = token_client.put(
            '/api/v1/organizers/{}/settings/'.format(organizer.slug),
            {'event_list_type': 'put-not-allowed'},
            format='json',
        )
        assert resp.status_code == 405

        resp = token_client.patch(
            '/api/v1/organizers/{}/settings/'.format(organizer.slug),
            {'primary_color': 'invalid-color'},
            format='json',
        )
        assert resp.status_code == 400

        resp = token_client.patch(
            '/api/v1/organizers/{}/settings/'.format(organizer.slug),
            {'primary_color': '#ff0000'},
            format='json',
        )
        assert resp.status_code == 200
        mocked.assert_any_call(args=(organizer.pk,))


@pytest.mark.django_db
def test_patch_organizer_settings_file(token_client, organizer):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'image/png',
            'file': ContentFile('file.png', 'invalid png content'),
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.png"',
    )
    assert r.status_code == 201
    file_id_png = r.data['id']

    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile('file.pdf', 'invalid pdf content'),
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.pdf"',
    )
    assert r.status_code == 201
    file_id_pdf = r.data['id']

    resp = token_client.patch(
        '/api/v1/organizers/{}/settings/'.format(organizer.slug),
        {'organizer_logo_image': 'invalid'},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.data == {'organizer_logo_image': ['The submitted file ID was not found.']}

    resp = token_client.patch(
        '/api/v1/organizers/{}/settings/'.format(organizer.slug),
        {'organizer_logo_image': file_id_pdf},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.data == {
        'organizer_logo_image': ['The submitted file has a file type that is not allowed in this field.']
    }

    resp = token_client.patch(
        '/api/v1/organizers/{}/settings/'.format(
            organizer.slug,
        ),
        {'organizer_logo_image': file_id_png},
        format='json',
    )
    assert resp.status_code == 200
    assert resp.data['organizer_logo_image'].startswith('http')

    resp = token_client.patch(
        '/api/v1/organizers/{}/settings/'.format(organizer.slug),
        {'organizer_logo_image': None},
        format='json',
    )
    assert resp.status_code == 200
    assert resp.data['organizer_logo_image'] is None




@pytest.fixture
@scopes_disabled()
def staff_user(user):
    """Create a staff user with active staff session."""
    user.is_staff = True
    user.save()
    session = user.staffsession_set.create(session_key='test-session')
    return user


@pytest.fixture
def staff_client(client, staff_user):
    """Create an authenticated client with staff session."""
    client.force_login(staff_user)
    return client


@pytest.mark.django_db
def test_organizer_list_staff_permission(staff_client, organizer, staff_user):
    """Test that staff user can see organizer list even without specific permission"""
    # We need to manually set the session key in the client's session
    # to match what StaffSessionMiddleware expects
    session = staff_client.session
    session.session_key = 'test-session'
    session.save()

    with scopes_disabled():
        resp = staff_client.get('/api/v1/organizers/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1


@pytest.mark.django_db
def test_organizer_detail_staff_permission(staff_client, organizer, staff_user):
    """Test that staff user can see organizer detail without specific permission"""
    session = staff_client.session
    session.session_key = 'test-session'
    session.save()

    with scopes_disabled():
        resp = staff_client.get('/api/v1/organizers/{}/'.format(organizer.slug))
        assert resp.status_code == 200
        assert resp.data['slug'] == organizer.slug


@pytest.mark.django_db
def test_organizer_settings_staff_permission(staff_client, organizer, staff_user):
    """Test that staff user can see organizer settings without specific permission"""
    session = staff_client.session
    session.session_key = 'test-session'
    session.save()

    with scopes_disabled():
        resp = staff_client.get('/api/v1/organizers/{}/settings/'.format(organizer.slug))
        assert resp.status_code == 200


@pytest.mark.django_db
def test_organizer_pagination_page_size(staff_client, organizer):
    """Test that page_size parameter works correctly."""
    with scopes_disabled():
        # Create 5 organizers total (including existing 'dummy')
        for i in range(4):
            Organizer.objects.create(name=f'Test Org {i}', slug=f'test-org-{i}')

    resp = staff_client.get('/api/v1/organizers/?page_size=1')
    assert resp.status_code == 200
    assert 'results' in resp.data
    assert len(resp.data['results']) == 1
    # Verify pagination metadata
    assert resp.data['count'] == 5


@pytest.mark.django_db
def test_organizer_pagination_max_cap(staff_client, organizer):
    """Test that max_page_size caps at 100 even if higher value requested."""
    with scopes_disabled():
        # Create 105 organizers to test the 100 cap
        for i in range(104):
            Organizer.objects.create(name=f'Test Org {i}', slug=f'test-org{i}')

    resp = staff_client.get('/api/v1/organizers/?page_size=999')
    assert resp.status_code == 200
    assert 'results' in resp.data
    # Should cap at max_page_size=100
    assert len(resp.data['results']) == 100
    assert resp.data['count'] == 105


@pytest.mark.django_db
def test_organizer_pagination_legacy_support(staff_client, organizer):
    """Test that legacy limit/offset pagination still works and overrides page parameter."""
    with scopes_disabled():
        # Create 15 organizers total
        for i in range(14):
            Organizer.objects.create(name=f'Test Org {i}', slug=f'testorg{i}')
    
    # Include both limit/offset and page to ensure limit/offset paginator is used
    resp = staff_client.get('/api/v1/organizers/?limit=10&offset=0&page=2')
    assert resp.status_code == 200
    assert 'results' in resp.data
    assert len(resp.data['results']) == 10
    # Legacy limit/offset pagination exposes count/next/previous with limit/offset in the URLs
    assert 'count' in resp.data
    assert 'next' in resp.data
    # Next URL should advance offset while preserving limit, demonstrating limit/offset-based pagination
    assert 'limit=10' in resp.data['next']
    assert 'offset=10' in resp.data['next']
    assert 'page=' not in resp.data['next']


