import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Product, SpeakerProfile, User


def _autocomplete_url(event):
    return event.orga_urls.speaker_autocomplete


def _autocomplete(client, event, search):
    return client.get(_autocomplete_url(event), data={'search': search})


def _event_scope(event):
    return scope(event=event, organizer=event.organizer)


def _create_order(event, *, email, status=Order.STATUS_PAID):
    with _event_scope(event):
        return Order.objects.create(
            event=event,
            status=status,
            datetime=now(),
            expires=now(),
            total=10,
            email=email,
            locale='en',
        )


def _create_product(event, *, admission=True, name='Ticket'):
    with _event_scope(event):
        return Product.objects.create(event=event, name=name, default_price=10, admission=admission)


def _create_attendee(
    event,
    *,
    email,
    name,
    status=Order.STATUS_PAID,
    admission=True,
    order=None,
    product=None,
    attendee_email=None,
):
    with _event_scope(event):
        product = product or _create_product(event, admission=admission)
        order = order or _create_order(event, email=email, status=status)
        return OrderPosition.objects.create(
            order=order,
            product=product,
            price=10,
            attendee_name_parts={'_legacy': name} if name else {},
            attendee_email=email if attendee_email is None else attendee_email,
            tax_rate=0,
            tax_value=0,
        )


def _create_same_organizer_event(event, *, slug='otherevt'):
    with scopes_disabled():
        other_event = Event.objects.create(
            name='Other event',
            is_public=True,
            slug=slug,
            email='other@orga.org',
            date_from=event.date_from,
            date_to=event.date_to,
            organizer=event.organizer,
        )
        for team in event.organizer.teams.all():
            team.limit_events.add(other_event)
    return other_event


@pytest.mark.django_db
def test_orga_autocomplete_requires_minimum_query(orga_client, event, speaker):
    response = _autocomplete(orga_client, event, 'Ja')

    assert response.status_code == 200
    assert response.json() == {'count': 0, 'results': []}


@pytest.mark.django_db
def test_orga_autocomplete_returns_event_speaker(orga_client, event, speaker):
    response = _autocomplete(orga_client, event, 'Jane S')

    assert response.status_code == 200
    content = response.json()
    assert content['count'] == 1
    assert content['results'][0]['email'] == speaker.email
    assert content['results'][0]['name'] == speaker.fullname
    assert speaker.email in content['results'][0]['label']


@pytest.mark.django_db
def test_orga_autocomplete_returns_proposal_submitter(orga_client, event, speaker, submission):
    with scope(event=event):
        speaker.profiles.filter(event=event).delete()

    response = _autocomplete(orga_client, event, 'jane@speaker')

    assert response.status_code == 200
    emails = [result['email'] for result in response.json()['results']]
    assert speaker.email in emails


@pytest.mark.django_db
def test_orga_autocomplete_returns_event_attendee(orga_client, event):
    _create_attendee(event, email='mario.attendee@example.com', name='Mario Attendee')

    response = _autocomplete(orga_client, event, 'Mario')

    assert response.status_code == 200
    content = response.json()
    assert content['count'] == 1
    assert content['results'][0]['email'] == 'mario.attendee@example.com'
    assert content['results'][0]['name'] == 'Mario Attendee'


@pytest.mark.django_db
def test_orga_autocomplete_deduplicates_speaker_and_attendee(orga_client, event, speaker):
    _create_attendee(event, email=speaker.email, name=speaker.fullname)

    response = _autocomplete(orga_client, event, 'Jane')

    assert response.status_code == 200
    emails = [result['email'] for result in response.json()['results']]
    assert emails.count(speaker.email) == 1


@pytest.mark.django_db
def test_orga_autocomplete_excludes_other_event_users(
    orga_client, event, speaker, other_event
):
    with scopes_disabled():
        foreign_user = User.objects.create_user(
            email='foreign@speaker.org',
            password='speakerpwd1!',
            fullname='Jane Foreign',
        )
    with scope(event=other_event):
        SpeakerProfile.objects.create(user=foreign_user, event=other_event)

    response = _autocomplete(orga_client, event, 'Jane')

    assert response.status_code == 200
    emails = [result['email'] for result in response.json()['results']]
    assert speaker.email in emails
    assert foreign_user.email not in emails


@pytest.mark.django_db
def test_orga_autocomplete_excludes_same_organizer_other_event(orga_client, event, speaker):
    other_event = _create_same_organizer_event(event)
    with scopes_disabled():
        sibling_user = User.objects.create_user(
            email='sibling@speaker.org',
            password='speakerpwd1!',
            fullname='Jane Sibling',
        )
    with scope(event=other_event):
        SpeakerProfile.objects.create(user=sibling_user, event=other_event)

    response = _autocomplete(orga_client, event, 'Jane')

    assert response.status_code == 200
    emails = [result['email'] for result in response.json()['results']]
    assert speaker.email in emails
    assert sibling_user.email not in emails


@pytest.mark.django_db
def test_orga_autocomplete_purchaser_email_does_not_return_named_attendees(orga_client, event):
    order = _create_order(event, email='buyer@example.com')
    product = _create_product(event)
    _create_attendee(event, email='bob@example.com', name='Bob Guest', order=order, product=product)
    _create_attendee(event, email='carol@example.com', name='Carol Guest', order=order, product=product)

    response = _autocomplete(orga_client, event, 'buyer@example')

    assert response.status_code == 200
    emails = [result['email'] for result in response.json()['results']]
    assert emails == []


@pytest.mark.django_db
def test_orga_autocomplete_purchaser_email_matches_ticket_without_attendee_email(orga_client, event):
    _create_attendee(
        event,
        email='buyer@example.com',
        name='Solo Buyer',
        attendee_email='',
    )

    response = _autocomplete(orga_client, event, 'buyer@example')

    assert response.status_code == 200
    content = response.json()
    assert content['count'] == 1
    assert content['results'][0]['email'] == 'buyer@example.com'
    assert content['results'][0]['name'] == 'Solo Buyer'


@pytest.mark.django_db
def test_orga_autocomplete_excludes_merchandise_purchaser(orga_client, event):
    _create_attendee(
        event,
        email='shirt.buyer@example.com',
        name='Shirt Buyer',
        admission=False,
    )

    response = _autocomplete(orga_client, event, 'shirt.buyer')

    assert response.status_code == 200
    assert response.json()['results'] == []


@pytest.mark.django_db
def test_orga_autocomplete_excludes_canceled_attendee(orga_client, event):
    _create_attendee(
        event,
        email='canceled@example.com',
        name='Canceled Guest',
        status=Order.STATUS_CANCELED,
    )

    response = _autocomplete(orga_client, event, 'Canceled')

    assert response.status_code == 200
    assert response.json()['results'] == []


@pytest.mark.django_db
def test_orga_autocomplete_no_platform_fallback(orga_client, event):
    with scopes_disabled():
        User.objects.create_user(
            email='platform.user@example.com',
            password='speakerpwd1!',
            fullname='Platform Jane',
        )

    response = _autocomplete(orga_client, event, 'Platform')

    assert response.status_code == 200
    assert response.json()['results'] == []


@pytest.mark.django_db
def test_submitter_cannot_access_event_autocomplete(speaker_client, event, speaker):
    response = _autocomplete(speaker_client, event, 'Jane')

    assert response.status_code == 404


@pytest.mark.django_db
def test_reviewer_cannot_access_event_autocomplete(review_client, event, speaker):
    response = _autocomplete(review_client, event, 'Jane')

    assert response.status_code == 404


@pytest.mark.django_db
def test_submitter_cannot_access_organizer_autocomplete(speaker_client, event, speaker):
    response = speaker_client.get(
        reverse('orga:organizer.user_list', kwargs={'organizer': event.organizer.slug}),
        data={'search': 'Jane'},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_organizer_legacy_user_search_returns_no_results(orga_client, event, speaker):
    response = orga_client.get(
        reverse('orga:organizer.user_list', kwargs={'organizer': event.organizer.slug}),
        data={'search': 'Jane'},
    )

    assert response.status_code == 200
    assert response.json() == {'count': 0, 'results': []}


@pytest.mark.django_db
def test_speaker_invite_page_has_no_autocomplete(speaker_client, submission):
    event = submission.event
    event.talks_published = True
    event.save()

    response = speaker_client.get(submission.urls.invite, follow=True)

    assert response.status_code == 200
    assert 'orga/js/speakers.js' not in response.text
    assert 'speaker-autocomplete' not in response.text
    assert 'remoteUrl' not in response.text
    assert 'autocomplete="off"' in response.text


@pytest.mark.django_db
def test_speaker_submission_edit_has_no_autocomplete(speaker_client, submission):
    event = submission.event
    event.talks_published = True
    event.save()

    response = speaker_client.get(submission.urls.user_base, follow=True)

    assert response.status_code == 200
    assert 'orga/js/speakers.js' not in response.text
    assert 'speaker-autocomplete' not in response.text
    assert 'remoteUrl' not in response.text
    assert 'autocomplete="off"' in response.text


@pytest.mark.django_db
def test_orga_create_proposal_uses_event_autocomplete(orga_client, event):
    response = orga_client.get(event.orga_urls.new_submission)

    assert response.status_code == 200
    assert event.orga_urls.speaker_autocomplete in response.text
    assert event.organizer.orga_urls.user_search not in response.text
    assert 'orga/js/speakers.js' in response.text
