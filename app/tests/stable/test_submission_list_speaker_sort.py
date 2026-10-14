import pytest
from django_scopes import scope

from eventyay.base.models import Submission, SubmissionType, User


@pytest.fixture
def orga_client(client, user, team):
    team.can_change_submissions = True
    team.is_reviewer = False
    team.save()
    client.force_login(user)
    return client


@pytest.fixture
def sessions(event):
    """Sessions whose speaker order differs from title and email order."""
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        zoe = User.objects.create_user(email='a-zoe@example.org', password='x', fullname='Zoe Zimmer')
        anna = User.objects.create_user(email='z-anna@example.org', password='x', fullname='anna Adler')
        mike = User.objects.create_user(email='mike@example.org', password='x', fullname='')

        def make(title, *speakers):
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


def _titles(response):
    return [submission.title for submission in response.context['submissions']]


@pytest.mark.django_db
class TestSessionListSpeakerSort:
    def test_ascending_sorts_by_first_speaker_and_puts_empty_last(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        assert response.status_code == 200
        assert _titles(response) == ['B panel', 'C talk by Mike', 'A talk by Zoe', 'D session without speaker']

    def test_descending_reverses_order_and_keeps_empty_last(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers'})

        assert response.status_code == 200
        assert _titles(response) == ['A talk by Zoe', 'C talk by Mike', 'B panel', 'D session without speaker']

    def test_speakers_cell_lists_first_speaker_first(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions, {'sort': 'speakers'})

        pair = next(s for s in response.context['submissions'] if s.title == 'B panel')
        assert [speaker.fullname for speaker in pair.speakers.all()] == ['anna Adler', 'Zoe Zimmer']

    def test_sort_combines_with_search(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers', 'q': 'talk'})

        assert response.status_code == 200
        assert _titles(response) == ['A talk by Zoe', 'C talk by Mike']

    def test_active_sort_link_is_marked(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions, {'sort': '-speakers'})
        content = response.content.decode()

        assert 'href="?sort=-speakers" class="sort-active" aria-current="true"' in content
        assert content.count('class="sort-active"') == 1

    def test_default_sort_marks_state(self, orga_client, event, sessions):
        response = orga_client.get(event.orga_urls.submissions)
        content = response.content.decode()

        assert 'href="?sort=state" class="sort-active" aria-current="true"' in content
