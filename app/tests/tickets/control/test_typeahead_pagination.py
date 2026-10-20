import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from eventyay.base.models import Event, Organizer, Product, Team, User


@pytest.mark.django_db
def test_product_typeahead_reports_no_more_at_exact_page_boundary(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Pagination Organizer', slug='pagination-organizer')
        event = Event.objects.create(
            organizer=organizer,
            name='Pagination Event',
            slug='pagination-event',
            date_from=now(),
        )
        user = User.objects.create_user('pagination@example.com', 'dummy')
        team = Team.objects.create(organizer=organizer, can_change_items=True, all_events=True)
        team.members.add(user)

        for index in range(20):
            Product.objects.create(event=event, name=f'Matching product {index:02d}', default_price=23)

    client.force_login(user)
    url = reverse(
        'control:event.products.select2',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = client.get(url, {'query': 'Matching product', 'page': 1})

    assert response.status_code == 200
    assert len(response.json()['results']) == 20
    assert response.json()['pagination']['more'] is False
