import pytest
from django.template.loader import render_to_string
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    Answer,
    Event,
    Organizer,
    ReviewPhase,
    SpeakerSocialLink,
    Submission,
    TalkQuestion,
    TalkQuestionRequired,
    TalkQuestionTarget,
    TalkQuestionVariant,
    Team,
    Track,
    User,
)
from eventyay.orga.utils.speakers import get_submission_answers, get_submission_speakers


@pytest.fixture
def event(db):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Display Org', slug='display-org')
        return Event.objects.create(
            name='Display Event',
            slug='display-event',
            email='display@example.org',
            date_from=now(),
            date_to=now(),
            organizer=organizer,
        )


@pytest.fixture
def speaker(event):
    with scopes_disabled():
        user = User.objects.create_user(email='speaker@example.org', password='password123', fullname='Speaker One')
        profile = user.event_profile(event)
        profile.biography = 'Infrastructure engineer.'
        profile.save()
        return user


@pytest.fixture
def orga_user(event):
    with scopes_disabled():
        return User.objects.create_user(email='orga@example.org', password='password123', fullname='Orga One')


@pytest.fixture
def submission(event, speaker):
    with scopes_disabled():
        submission = Submission.objects.create(
            title='Open models are easy',
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        submission.speakers.add(speaker)
        return submission


def make_question(event, target, question, *, visible_to_reviewers=True, position=0, variant=None):
    return TalkQuestion.all_objects.create(
        event=event,
        question=question,
        variant=variant or TalkQuestionVariant.STRING,
        target=target,
        question_required=TalkQuestionRequired.OPTIONAL,
        active=True,
        position=position,
        is_visible_to_reviewers=visible_to_reviewers,
    )


@pytest.mark.django_db
def test_organisers_see_speaker_questions_hidden_from_reviewers(event, speaker, submission, orga_user):
    with scopes_disabled():
        hidden = make_question(
            event, TalkQuestionTarget.SPEAKER, 'Relationship with the topic?', visible_to_reviewers=False
        )
        shown = make_question(event, TalkQuestionTarget.SPEAKER, 'Do you have a ticket?', position=1)
        Answer.objects.create(question=hidden, person=speaker, answer='Creator')
        Answer.objects.create(question=shown, person=speaker, answer='No')

    with scope(event=event):
        for_orga = get_submission_speakers(submission, for_reviewers=False, user=orga_user)
        for_reviewers = get_submission_speakers(submission, for_reviewers=True, user=orga_user)

    assert [answer.question.question for answer in for_orga[0].answers] == [
        'Relationship with the topic?',
        'Do you have a ticket?',
    ]
    assert [answer.question.question for answer in for_reviewers[0].answers] == ['Do you have a ticket?']


@pytest.mark.django_db
def test_speaker_details_carry_social_links_and_other_proposals(event, speaker, submission, orga_user):
    with scopes_disabled():
        profile = speaker.event_profile(event)
        SpeakerSocialLink.objects.create(profile=profile, network='github', url='https://github.com/speaker-one')
        other = Submission.objects.create(
            title='A second proposal',
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        other.speakers.add(speaker)

    with scope(event=event):
        speakers = get_submission_speakers(submission, for_reviewers=False, user=orga_user)

    assert len(speakers) == 1
    details = speakers[0]
    assert details.profile.biography == 'Infrastructure engineer.'
    assert [link.url for link in details.social_links] == ['https://github.com/speaker-one']
    assert [other.title for other in details.other_submissions] == ['A second proposal']


@pytest.mark.django_db
def test_inactive_speaker_questions_are_left_out(event, speaker, submission, orga_user):
    with scopes_disabled():
        question = make_question(event, TalkQuestionTarget.SPEAKER, 'Retired field?')
        Answer.objects.create(question=question, person=speaker, answer='Still here')
        question.active = False
        question.save()

    with scope(event=event):
        speakers = get_submission_speakers(submission, for_reviewers=False, user=orga_user)

    assert speakers[0].answers == ()


@pytest.mark.django_db
def test_reviewers_only_see_other_proposals_they_may_review(event, speaker, submission, orga_user):
    with scopes_disabled():
        reviewer = User.objects.create_user(email='reviewer@example.org', password='password123', fullname='Reviewer')
        reviewed_track = Track.objects.create(event=event, name='Reviewed track', color='#00ff00')
        other_track = Track.objects.create(event=event, name='Other track', color='#ff0000')
        team = Team.objects.create(organizer=event.organizer, name='Reviewers', is_reviewer=True)
        team.limit_events.add(event)
        team.limit_tracks.add(reviewed_track)
        team.members.add(reviewer)
        ReviewPhase.objects.create(event=event, name='Review', is_active=True, proposal_visibility='all')
        submission.track = reviewed_track
        submission.save()
        for title, track in (('In my tracks', reviewed_track), ('Out of my tracks', other_track)):
            other = Submission.objects.create(
                title=title,
                event=event,
                submission_type=event.cfp.default_type,
                track=track,
                content_locale='en',
            )
            other.speakers.add(speaker)

    with scope(event=event):
        for_orga = get_submission_speakers(submission, for_reviewers=False, user=orga_user)
        for_reviewers = get_submission_speakers(submission, for_reviewers=True, user=reviewer)

    assert sorted(other.title for other in for_orga[0].other_submissions) == [
        'In my tracks',
        'Out of my tracks',
    ]
    assert [other.title for other in for_reviewers[0].other_submissions] == ['In my tracks']

    with scope(event=event):
        assert [other.viewer_url for other in for_orga[0].other_submissions] == [
            other.orga_urls.base for other in for_orga[0].other_submissions
        ]
        assert [other.viewer_url for other in for_reviewers[0].other_submissions] == [
            other.orga_urls.reviews for other in for_reviewers[0].other_submissions
        ]


@pytest.mark.django_db
def test_imported_questions_are_left_out(event, speaker, submission, orga_user):
    with scopes_disabled():
        speaker_question = make_question(event, TalkQuestionTarget.SPEAKER, 'Imported speaker field')
        speaker_question.is_imported = True
        speaker_question.save()
        Answer.objects.create(question=speaker_question, person=speaker, answer='From the import')
        proposal_question = make_question(event, TalkQuestionTarget.SUBMISSION, 'Imported proposal field')
        proposal_question.is_imported = True
        proposal_question.save()
        Answer.objects.create(question=proposal_question, submission=submission, answer='From the import')

    with scope(event=event):
        speakers = get_submission_speakers(submission, for_reviewers=False, user=orga_user)
        answers = get_submission_answers(submission, for_reviewers=False)

    assert speakers[0].answers == ()
    assert answers == []


@pytest.mark.django_db
def test_proposal_answers_follow_question_order_and_reviewer_visibility(event, submission):
    with scopes_disabled():
        second = make_question(event, TalkQuestionTarget.SUBMISSION, 'Target audience', position=2)
        first = make_question(
            event, TalkQuestionTarget.SUBMISSION, 'Technical level', position=1, visible_to_reviewers=False
        )
        make_question(event, TalkQuestionTarget.SUBMISSION, 'Unanswered optional field', position=3)
        Answer.objects.create(question=second, submission=submission, answer='Platform teams')
        Answer.objects.create(question=first, submission=submission, answer='Advanced')

    with scope(event=event):
        for_orga = get_submission_answers(submission, for_reviewers=False)
        for_reviewers = get_submission_answers(submission, for_reviewers=True)

    assert [answer.question.question for answer in for_orga] == ['Technical level', 'Target audience']
    assert [answer.question.question for answer in for_reviewers] == ['Target audience']


@pytest.mark.django_db
def test_answer_list_skips_unanswered_fields(event, submission):
    with scopes_disabled():
        answered = make_question(event, TalkQuestionTarget.SUBMISSION, 'Target audience')
        blank = make_question(event, TalkQuestionTarget.SUBMISSION, 'Special requirements', position=1)
        answers = [
            Answer.objects.create(question=answered, submission=submission, answer='Platform teams'),
            Answer.objects.create(question=blank, submission=submission, answer=''),
        ]

    with scope(event=event):
        html = render_to_string('orga/includes/submission_answers.html', {'answers': answers})

    assert 'Target audience' in html
    assert 'Platform teams' in html
    assert 'Special requirements' not in html


@pytest.mark.django_db
def test_social_links_render_as_labelled_links(event, speaker):
    with scopes_disabled():
        profile = speaker.event_profile(event)
        link = SpeakerSocialLink.objects.create(profile=profile, network='github', url='https://github.com/speaker-one')

    html = render_to_string('orga/includes/speaker_social_links.html', {'social_links': [link]})

    assert 'GitHub' in html
    assert 'href="https://github.com/speaker-one"' in html
    assert 'fa-github' in html


def test_social_links_render_nothing_without_links():
    assert render_to_string('orga/includes/speaker_social_links.html', {'social_links': []}).strip() == ''
