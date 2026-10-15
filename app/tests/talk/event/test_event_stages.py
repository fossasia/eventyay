import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.event.stages import STAGE_ORDER, in_stage


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target,is_public,from_delta,to_delta,deadline_delta,has_submissions",
    (
        ("PREPARATION", False, 2, 3, 1, False),
        ("PREPARATION", False, 2, 3, 1, True),
        ("CFP_OPEN", True, 2, 3, 1, False),
        ("CFP_OPEN", True, 2, 3, 1, True),
        ("REVIEW", True, 2, 3, -1, True),
        ("SCHEDULE", True, 2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, False),
        ("EVENT", True, -2, 3, -1, True),
        ("EVENT", True, 0, 0, -1, False),
        ("EVENT", True, 0, 0, -1, True),
        ("WRAPUP", True, -2, -1, -1, True),
        ("WRAPUP", True, -2, -1, -1, False),
    ),
)
def test_event_stages(
    event,
    submission,
    target,
    is_public,
    from_delta,
    to_delta,
    deadline_delta,
    has_submissions,
):
    with scope(event=event):
        _now = now()
        event.is_public = is_public
        event.talks_published = is_public
        if from_delta == 0 and to_delta == 0:
            event.date_from = _now - dt.timedelta(hours=2)
            event.date_to = _now + dt.timedelta(hours=2)
        else:
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
            if stage == target and target != "WRAPUP":
                break


@pytest.mark.django_db
def test_newly_created_event_stages(event):
    """A newly created event with talks_published=False must be in Preparation."""
    from eventyay.event.stages import get_stages
    from eventyay.orga.views.dashboard import EventDashboardView

    with scope(event=event):
        event.talks_published = False
        event.date_from = now() + dt.timedelta(days=30)
        event.date_to = now() + dt.timedelta(days=32)
        event.save()

        stages = get_stages(event)
        assert stages['PREPARATION']['phase'] == 'current'
        assert stages['PREPARATION']['name'] == 'Preparation'
        assert stages['CFP_OPEN']['phase'] == 'todo'
        assert stages['CFP_OPEN']['name'] == 'CfP'
        assert stages['REVIEW']['phase'] == 'todo'
        assert stages['SCHEDULE']['phase'] == 'todo'
        assert stages['EVENT']['phase'] == 'todo'
        assert stages['WRAPUP']['phase'] == 'todo'

        view = EventDashboardView()
        timeline = view.enhance_timeline(event, stages)
        prep = next(s for s in timeline if s['name'] == 'Preparation')
        assert prep['status_text'] == 'In progress'
        assert prep['phase'] == 'current'

        cfp = next(s for s in timeline if s['name'] == 'CfP')
        assert cfp['status_text'] == 'Pending'
        assert cfp['phase'] == 'todo'


@pytest.mark.django_db
def test_published_event_with_open_cfp_stages(event):
    """When talks are published and CfP is open, CfP is open is current and Preparation is completed."""
    from eventyay.event.stages import get_stages
    from eventyay.orga.views.dashboard import EventDashboardView

    with scope(event=event):
        event.talks_published = True
        event.date_from = now() + dt.timedelta(days=30)
        event.date_to = now() + dt.timedelta(days=32)
        event.cfp.deadline = now() + dt.timedelta(days=10)
        event.save()
        event.cfp.save()

        stages = get_stages(event)
        assert stages['PREPARATION']['phase'] == 'done'
        assert stages['CFP_OPEN']['phase'] == 'current'
        assert stages['CFP_OPEN']['name'] == 'CfP is open'
        assert stages['REVIEW']['phase'] == 'todo'

        view = EventDashboardView()
        timeline = view.enhance_timeline(event, stages)
        prep = next(s for s in timeline if s['name'] == 'Preparation')
        assert prep['status_text'] == 'Completed'
        assert prep['phase'] == 'done'

        cfp = next(s for s in timeline if s['name'] == 'CfP is open')
        assert cfp['status_text'] == 'In progress'
        assert cfp['phase'] == 'current'

