import re

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from django_scopes import scope, scopes_disabled

from eventyay.base.models import LogEntry, User


def user_option(response, user):
    match = re.search(rf'<option value="{user.pk}"[^>]*>', response.content.decode(), re.S)
    assert match, f'no option for user {user.pk}'
    return match.group(0)


def create_log(obj, user, event=None):
    return LogEntry.objects.create(
        event=event,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        user=user,
        action_type='test.user.filter',
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('page', ['event', 'organizer'])
def test_log_user_filter_keeps_the_selected_team_member(organizer_client, organizer, event, user, page):
    with scopes_disabled():
        other_user = User.objects.create_user('other@example.com', 'other')

    if page == 'event':
        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        with scope(event=event):
            selected_log = create_log(event, user, event=event)
            create_log(event, other_user, event=event)
    else:
        url = reverse('control:organizer.log', kwargs={'organizer': organizer.slug})
        with scopes_disabled():
            selected_log = create_log(organizer, user)
            create_log(organizer, other_user)

    response = organizer_client.get(url)
    assert response.status_code == 200
    assert 'selected' not in user_option(response, user)

    response = organizer_client.get(url, {'user': user.pk})
    assert response.status_code == 200
    assert 'selected="selected"' in user_option(response, user)
    assert list(response.context['logs']) == [selected_log]
