import pytest
from django_scopes import scope


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "never", "after_schedule"))
def test_featured_invisible_because_setting(
    client, django_assert_max_num_queries, event, featured, confirmed_submission
):
    with scope(event=event):
        event.feature_flags["show_featured"] = featured
        event.save()
        confirmed_submission.is_featured = True
        confirmed_submission.save()
    url = str(event.urls.featured)
    with django_assert_max_num_queries(9):
        response = client.get(url, follow=True)
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 200
        url = url.replace("featured", "sneak")
        response = client.get(url)
        assert response.status_code == 301
        assert response.url == event.urls.featured


@pytest.mark.django_db
def test_featured_invisible_when_setting_unset(
    client, django_assert_max_num_queries, event, confirmed_submission
):
    with scope(event=event):
        event.feature_flags.pop("show_featured", None)
        event.save()
        confirmed_submission.is_featured = True
        confirmed_submission.save()
    with django_assert_max_num_queries(9):
        response = client.get(event.urls.featured, follow=True)
    assert response.status_code == 404


@pytest.mark.parametrize("featured", ("always", "never", "after_schedule"))
@pytest.mark.django_db
def test_featured_invisible_because_schedule(
    client, django_assert_max_num_queries, event, featured
):
    with scope(event=event):
        event.feature_flags["show_featured"] = featured
        event.save()
        event.release_schedule("42")
    with django_assert_max_num_queries(8):
        response = client.get(event.urls.featured)

    if featured == "always":
        assert response.status_code == 200
    else:
        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "after_schedule"))
def test_featured_visible_despite_schedule(
    client, django_assert_max_num_queries, event, featured
):
    event.feature_flags["show_featured"] = featured
    event.feature_flags["show_schedule"] = False
    event.save()
    with scope(event=event):
        event.release_schedule("42")
    with django_assert_max_num_queries(8):
        response = client.get(event.urls.featured, follow=True)
    assert response.status_code == 200
    assert "featured" in response.text


@pytest.mark.django_db
def test_featured_talk_list(
    client,
    django_assert_max_num_queries,
    event,
    confirmed_submission,
    other_confirmed_submission,
):
    confirmed_submission.is_featured = True
    confirmed_submission.save()

    event.feature_flags["show_featured"] = True
    event.save()

    with django_assert_max_num_queries(9):
        response = client.get(event.urls.featured, follow=True)
    assert response.status_code == 200
    content = response.text
    assert confirmed_submission.title in content
    assert other_confirmed_submission.title not in content


@pytest.mark.django_db
def test_featured_never_blocks_admin_mode_direct_url(client, event, administrator, confirmed_submission, monkeypatch):
    with scope(event=event):
        event.feature_flags['show_featured'] = 'never'
        event.save()
        confirmed_submission.is_featured = True
        confirmed_submission.save()

    monkeypatch.setattr(type(administrator), 'has_active_staff_session', lambda self, session_key: True)
    client.force_login(administrator)

    response = client.get(event.urls.featured)
    assert response.status_code == 404
