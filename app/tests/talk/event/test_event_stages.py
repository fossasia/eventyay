import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.event.stages import STAGE_ORDER, get_stages, in_stage


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target,talks_published,from_delta,to_delta,deadline_delta,has_submissions",
    (
        ("PREPARATION", False, 2, 3, 1, False),
        ("PREPARATION", False, 2, 3, 1, True),
        ("PREPARATION", False, 2, 3, -1, True),
        ("CFP_OPEN", True, 2, 3, 1, False),
        ("CFP_OPEN", True, 2, 3, 1, True),
        ("REVIEW", True, 2, 3, -1, True),
        ("SCHEDULE", True, 2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, True),
        ("EVENT", True, -2, 3, 1, True),
        ("EVENT", False, -2, 3, 1, False),
        ("EVENT", True, 0, 3, -1, False),
        ("WRAPUP", True, -2, 0, -1, True),
        ("WRAPUP", True, -2, -1, -1, True),
        ("WRAPUP", True, -2, -1, -1, False),
        ("WRAPUP", True, -2, -1, 1, True),
        ("WRAPUP", False, -2, -1, 1, False),
    ),
)
def test_event_stages(
    event,
    submission,
    target,
    talks_published,
    from_delta,
    to_delta,
    deadline_delta,
    has_submissions,
    monkeypatch,
):
    """Select one phase from Talks publication, CfP state, submissions and dates."""
    with scope(event=event):
        _now = now()
        monkeypatch.setattr('eventyay.event.stages.now', lambda: _now)
        event.is_public = True
        event.talks_published = talks_published
        event.date_from = _now + dt.timedelta(days=from_delta)
        event.date_to = _now + dt.timedelta(days=to_delta)
        event.cfp.deadline = _now + dt.timedelta(days=deadline_delta)
        event.save()
        event.cfp.save()
        event = event.__class__.objects.get(pk=event.pk)
        if not has_submissions:
            submission.state = "DELETED"
            submission.save()
        for stage in STAGE_ORDER:
            assert in_stage(event, stage) == (
                stage == target
            ), f'Event is{" not" if stage == target else ""} {stage} when it should be {target}!'
        stages = get_stages(event)
        target_index = STAGE_ORDER.index(target)
        for index, stage in enumerate(STAGE_ORDER):
            expected = 'done' if index < target_index else 'current' if index == target_index else 'todo'
            assert stages[stage]['phase'] == expected
        assert str(stages['CFP_OPEN']['name']) == ('CfP is open' if target == 'CFP_OPEN' else 'CfP')


@pytest.mark.django_db
@pytest.mark.parametrize('is_public', (True, False))
def test_new_event_starts_in_preparation(event, is_public):
    """Keep a new event in Preparation regardless of its event-list visibility."""
    with scope(event=event):
        event.date_from = now() + dt.timedelta(days=2)
        event.date_to = event.date_from + dt.timedelta(days=1)
        event.is_public = is_public
        assert event.talks_published is False
        assert event.cfp.is_open is True
        stages = get_stages(event)
        assert stages['PREPARATION']['phase'] == 'current'
        assert all(stages[stage]['phase'] == 'todo' for stage in STAGE_ORDER[1:])
        assert str(stages['CFP_OPEN']['name']) == 'CfP'
