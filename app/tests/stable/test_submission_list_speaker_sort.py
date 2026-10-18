import re

import pytest
from django.http import HttpResponse
from django.test import Client
from django_scopes import scope

from eventyay.base.models import Submission, SubmissionType, User
from eventyay.base.models.auth import StaffSession


@pytest.fixture
def orga_client(client: Client, user: User, team) -> Client:
    team.can_change_submissions = True
    team.is_reviewer = False
    team.save()
    client.force_login(user)
    return client


@pytest.fixture
def sessions(event) -> dict[str, Submission]:
    """Sessions whose speaker order differs from title and email order."""
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        zoe = User.objects.create_user(email='a-zoe@example.org', password='x', fullname='Zoe Zimmer')
        anna = User.objects.create_user(email='z-anna@example.org', password='x', fullname='anna Adler')
        mike = User.objects.create_user(email='mike@example.org', password='x', fullname='')

        def make(title: str, *speakers: User) -> Submission:
            submission = Submission.objects.create(
                title=title,
                event=event,
                submission_type=submission_type,
                abstract='Abstract',
                content_locale='en',
            )
            submission.speakers.add(*speakers)
            return submission

        return {
            'zoe': make('A talk by Zoe', zoe),
            # Listed by its alphabetically first speaker, Anna, not by Zoe.
            'pair': make('B panel', zoe, anna),
            # No full name: the email is shown and used instead.
            'mike': make('C talk by Mike', mike),
            'nobody': make('D session without speaker'),
        }


def _titles(response: HttpResponse) -> list[str]:
    return [submission.title for submission in response.context['submissions']]


def _thead(response: HttpResponse) -> str:
    return response.content.decode().split('<thead>')[1].split('</thead>')[0]


def _active_sort_hrefs(response: HttpResponse) -> list[str]:
    return re.findall(r'<a href="([^"]*)" class="sort-link sort-active" aria-current="true"', _thead(response))


@pytest.mark.django_db
class TestSessionListSpeakerSort:
    def test_ascending_sorts_by_first_speaker_and_puts_empty_last(self, orga_client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        assert response.status_code == 200
        assert _titles(response) == ['B panel', 'C talk by Mike', 'A talk by Zoe', 'D session without speaker']

    def test_descending_reverses_order_and_keeps_empty_last(self, orga_client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers'})

        assert response.status_code == 200
        assert _titles(response) == ['A talk by Zoe', 'C talk by Mike', 'B panel', 'D session without speaker']

    def test_speaker_without_name_or_email_sorts_by_nick(self, orga_client, event, sessions) -> None:
        with scope(event=event):
            quinn = User.objects.create(email=None, fullname=None, nick='Quinn')
            submission = Submission.objects.create(
                title='E talk by Quinn',
                event=event,
                submission_type=sessions['zoe'].submission_type,
                abstract='Abstract',
                content_locale='en',
            )
            submission.speakers.add(quinn)

        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        assert _titles(response) == [
            'B panel',
            'C talk by Mike',
            'E talk by Quinn',
            'A talk by Zoe',
            'D session without speaker',
        ]

    def test_speaker_name_is_trimmed_before_sorting(self, orga_client, event, sessions) -> None:
        with scope(event=event):
            zed = User.objects.create_user(email='zed@example.org', password='x', fullname='  Zed Zander')
            # Whitespace only: sorts by the email, like a missing name.
            kim = User.objects.create_user(email='kim@example.org', password='x', fullname='   ')
            for title, speaker in (('F talk by Zed', zed), ('G talk by Kim', kim)):
                submission = Submission.objects.create(
                    title=title,
                    event=event,
                    submission_type=sessions['zoe'].submission_type,
                    abstract='Abstract',
                    content_locale='en',
                )
                submission.speakers.add(speaker)

        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        assert _titles(response) == [
            'B panel',
            'G talk by Kim',
            'C talk by Mike',
            'F talk by Zed',
            'A talk by Zoe',
            'D session without speaker',
        ]

    def test_speakers_cell_lists_first_speaker_first(self, orga_client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        pair = next(s for s in response.context['submissions'] if s.title == 'B panel')
        assert [speaker.fullname for speaker in pair.speakers.all()] == ['anna Adler', 'Zoe Zimmer']

    def test_sort_combines_with_search(self, orga_client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers', 'q': 'talk'})

        assert response.status_code == 200
        assert _titles(response) == ['A talk by Zoe', 'C talk by Mike']

    def test_active_sort_link_is_marked(self, orga_client: Client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers'})

        assert _active_sort_hrefs(response) == ['?sort=-speakers']

    def test_sort_links_reset_page_and_keep_filters(self, orga_client: Client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions, {'q': 'talk', 'page': '1', 'sort': 'title'})
        hrefs = re.findall(r'<a href="([^"]*)" class="sort-link', _thead(response))

        assert any('sort=speakers' in href for href in hrefs)
        assert all('page=' not in href and 'q=talk' in href for href in hrefs)

    def test_sort_links_have_accessible_names(self, orga_client: Client, event, sessions) -> None:
        links = re.findall(r'<a href="[^"]*" class="sort-link[^>]*>.*?</a>', _thead(orga_client.get(event.orga_urls.submissions)))

        assert len(links) >= 8
        for link in links:
            title = re.search(r' title="([^"]+)"', link).group(1)
            assert f'aria-label="{title}"' in link
            assert 'aria-hidden="true"' in link
        assert any('aria-label="Sort by speaker (a-z)"' in link for link in links)
        assert any('aria-label="Sort featured sessions first"' in link for link in links)

    def test_admin_mode_without_team_permission_sorts_by_speaker(self, client, staff_user, event, sessions) -> None:
        client.force_login(staff_user)
        session = client.session
        session.save()
        StaffSession.objects.create(user=staff_user, session_key=session.session_key)

        response = client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        assert response.status_code == 200
        assert _titles(response) == ['B panel', 'C talk by Mike', 'A talk by Zoe', 'D session without speaker']

    def test_hidden_speaker_names_ignore_speaker_sort(self, orga_client, user, team, event, sessions) -> None:
        team.force_hide_speaker_names = True
        team.save()
        assert not user.has_perm('base.orga_list_speakerprofile', event)

        default = orga_client.get(event.orga_urls.submissions)
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers'})

        assert response.status_code == 200
        # Sorting by speaker would reveal the hidden names, so the default order is kept.
        assert _titles(response) == _titles(default)
        assert _titles(response) != ['A talk by Zoe', 'C talk by Mike', 'B panel', 'D session without speaker']
        thead = _thead(response)
        assert 'sort=-speakers' not in thead
        assert 'sort=speakers' not in thead
        assert _active_sort_hrefs(response) == ['?sort=state']

    def test_default_sort_marks_state(self, orga_client, event, sessions) -> None:
        response = orga_client.get(event.orga_urls.submissions)

        assert _active_sort_hrefs(response) == ['?sort=state']
