"""Shared speaker data collection for the organiser submission pages.

The Speakers and Reviews tabs both need the complete submitted information for
every speaker on a proposal. Collecting it in one place keeps the two pages
from drifting apart, and keeps the prefetching in one query plan.
"""

from dataclasses import dataclass

from django.db.models import Prefetch, Q
from django_scopes import scope

from eventyay.base.models import (
    Answer,
    SpeakerProfile,
    Submission,
    TalkQuestion,
    TalkQuestionTarget,
    User,
)
from eventyay.common.session_video import exclude_session_video_from_cfp_questions
from eventyay.talk_rules.submission import limit_for_reviewers


@dataclass(frozen=True)
class SubmissionSpeaker:
    """Everything the organiser submission pages show about one speaker."""

    user: User
    profile: SpeakerProfile | None
    email: str
    avatar: object
    avatar_url: str
    avatar_source: str
    avatar_license: str
    answers: tuple[Answer, ...]
    social_links: tuple[object, ...]
    other_submissions: tuple[Submission, ...]


def _with_viewer_url(other: Submission, *, for_reviewers: bool) -> Submission:
    """Point one of a speaker's other proposals at the page the viewer may open.

    Reviewers have no access to the organiser submission view, so their links
    lead to that proposal's review page instead of failing authorisation.
    """
    other.viewer_url = other.orga_urls.reviews if for_reviewers else other.orga_urls.base
    return other


def get_submission_speakers(submission: Submission, *, for_reviewers: bool, user: User) -> list[SubmissionSpeaker]:
    """Collect the full speaker information for a proposal.

    ``for_reviewers`` restricts the custom speaker fields to the questions the
    event marked as visible to reviewers. Organisers see every active speaker
    question instead, which is what they filled the CfP form with.

    ``user`` is the viewer. For reviewers, the speaker's other proposals are
    limited to the ones that viewer is allowed to review, so the fragment never
    leaks the title or state of a proposal outside their tracks or assignment,
    and each one is linked to the page that viewer may actually open.
    """
    event = submission.event
    with scope(event=event):
        answers = (
            Answer.objects.filter(
                question__event=event,
                question__active=True,
                question__is_imported=False,
                question__target=TalkQuestionTarget.SPEAKER,
            )
            .select_related('question')
            .order_by('question__position')
        )
        other_submissions = Submission.objects.filter(event=event)
        if for_reviewers:
            answers = answers.filter(question__is_visible_to_reviewers=True)
            other_submissions = limit_for_reviewers(other_submissions, event, user)

        speakers = submission.speakers.all().prefetch_related(
            Prefetch(
                'profiles',
                queryset=SpeakerProfile.objects.filter(event=event).prefetch_related('availabilities', 'social_links'),
                to_attr='_event_profiles',
            ),
            Prefetch('answers', queryset=answers, to_attr='_speaker_answers'),
            Prefetch('submissions', queryset=other_submissions, to_attr='_event_submissions'),
        )

        result = []
        for speaker in speakers:
            profile = speaker.event_profile(event)
            result.append(
                SubmissionSpeaker(
                    user=speaker,
                    profile=profile,
                    email=speaker.email,
                    avatar=speaker.avatar,
                    avatar_url=speaker.get_avatar_url(event=event),
                    avatar_source=speaker.avatar_source,
                    avatar_license=speaker.avatar_license,
                    answers=tuple(speaker._speaker_answers),
                    social_links=tuple(profile.social_links.all()) if profile else (),
                    other_submissions=tuple(
                        _with_viewer_url(other, for_reviewers=for_reviewers)
                        for other in speaker._event_submissions
                        if other.code != submission.code
                    ),
                )
            )
        return result


def viewer_is_reviewer_only(user: User, event) -> bool:
    """Whether this user sees the event as a reviewer rather than as an organiser."""
    return not user.has_perm('base.orga_update_submission', event) and user.has_perm('base.list_review', event)


def get_submission_answers(submission: Submission, *, for_reviewers: bool) -> list[Answer]:
    """Collect the answers to the event's custom proposal fields, in configured order.

    The question set mirrors the one the CfP form built for this proposal, so
    the Content tab shows exactly the fields the speaker was asked, including
    the ones limited to the proposal's track or session type.
    """
    event = submission.event
    with scope(event=event):
        questions = TalkQuestion.all_objects.filter(
            event=event,
            active=True,
            is_imported=False,
            target=TalkQuestionTarget.SUBMISSION,
        )
        questions = exclude_session_video_from_cfp_questions(questions)
        if submission.track_id:
            questions = questions.filter(Q(tracks=submission.track_id) | Q(tracks__isnull=True))
        if submission.submission_type_id:
            questions = questions.filter(
                Q(submission_types=submission.submission_type_id) | Q(submission_types__isnull=True)
            )
        if for_reviewers:
            questions = questions.filter(is_visible_to_reviewers=True)
        return list(
            Answer.objects.filter(submission=submission, question__in=questions)
            .select_related('question')
            .order_by('question__position')
        )
