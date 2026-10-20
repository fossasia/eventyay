import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from eventyay.base.models import Event, Order, Organizer, Team, User


@pytest.mark.django_db
def test_nav_typeahead_paginates_matching_orders(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Search Organizer', slug='search-organizer')
        event = Event.objects.create(
            organizer=organizer,
            name='Unrelated Event',
            slug='unrelated-event',
            date_from=now(),
        )
        user = User.objects.create_user('nav-search@example.com', 'dummy')
        team = Team.objects.create(organizer=organizer, can_view_orders=True, all_events=True)
        team.members.add(user)

        for index in range(21):
            Order.objects.create(
                code=f'ORDERMATCH{index:02d}',
                event=event,
                email='buyer@example.com',
                status=Order.STATUS_PAID,
                datetime=now(),
                total=0,
            )

    client.force_login(user)
    url = reverse('control:nav.typeahead')

    first_page = client.get(url, {'query': 'ORDERMATCH'})
    assert first_page.status_code == 200
    assert first_page.json()['pagination']['more'] is True
    assert len([result for result in first_page.json()['results'] if result['type'] == 'order']) == 20

    second_page = client.get(url, {'query': 'ORDERMATCH', 'page': 2})
    assert second_page.status_code == 200
    assert second_page.json()['pagination']['more'] is False
    assert len([result for result in second_page.json()['results'] if result['type'] == 'order']) == 1
