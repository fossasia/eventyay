import datetime as dt

from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import TalkQuestion, TalkQuestionTarget
from eventyay.base.models.cfp import SPEAKER_JOB_TITLE_IMPORT_KEY, SPEAKER_ORGANIZATION_IMPORT_KEY
from eventyay.base.models.question import Answer


def create_user(email, name=None, pw_reset_days=60, event=None):
    from eventyay.base.models import SpeakerProfile, User

    user = User.objects.create_user(
        password=get_random_string(32),
        email=email.lower().strip(),
        fullname=(name or '').strip(),
        pw_reset_token=get_random_string(32),
        pw_reset_time=now() + dt.timedelta(days=pw_reset_days),
    )
    if event:
        SpeakerProfile.objects.get_or_create(user=user, event=event)
    return user


def get_public_speaker_role_questions(event):
    """Return public Job Title and Organization questions for this event, if any."""
    with scope(event=event):
        questions = {
            q.import_key: q
            for q in TalkQuestion.objects.filter(
                event=event,
                target=TalkQuestionTarget.SPEAKER,
                is_public=True,
                import_key__in=[SPEAKER_JOB_TITLE_IMPORT_KEY, SPEAKER_ORGANIZATION_IMPORT_KEY],
            )
        }
    return questions.get(SPEAKER_JOB_TITLE_IMPORT_KEY), questions.get(SPEAKER_ORGANIZATION_IMPORT_KEY)


def build_speaker_role_answers_map(user_ids, job_title_q, org_q, event):
    """Prefetch public speaker-role answers for the given user IDs.

    Returns a dict mapping user_id -> role string (e.g. "Engineer, Acme").
    """
    if not user_ids or (not job_title_q and not org_q):
        return {}

    question_ids = [q.pk for q in (job_title_q, org_q) if q]
    with scope(event=event):
        answers = list(
            Answer.objects.filter(
                question_id__in=question_ids,
                person_id__in=user_ids,
            ).values('person_id', 'question_id', 'answer')
        )

    job_title_qid = job_title_q.pk if job_title_q else None
    org_qid = org_q.pk if org_q else None

    by_user: dict[int, dict] = {}
    for row in answers:
        by_user.setdefault(row['person_id'], {})[row['question_id']] = row['answer']

    result = {}
    for user_id in user_ids:
        user_answers = by_user.get(user_id, {})
        parts = []
        if job_title_qid and (user_answers.get(job_title_qid) or '').strip():
            parts.append((user_answers[job_title_qid] or '').strip())
        if org_qid and (user_answers.get(org_qid) or '').strip():
            parts.append((user_answers[org_qid] or '').strip())
        if parts:
            result[user_id] = ', '.join(parts)
    return result
