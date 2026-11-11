import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.event.stages import STAGE_ORDER, get_stages, in_stage


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
        event.date_from = (_now + dt.timedelta(days=from_delta)).date()
        event.date_to = (_now + dt.timedelta(days=to_delta)).date()
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
def test_newly_created_event_stage(event):
    with scope(event=event):
        # A newly created event has is_public=True by default, but talks_published=False
        event.is_public = True
        event.talks_published = False
        event.date_from = (now() + dt.timedelta(days=2)).date()
        event.date_to = (now() + dt.timedelta(days=5)).date()
        event.save()

        stages = get_stages(event)
        # Preparation must not automatically be marked Completed
        assert stages['PREPARATION']['phase'] == 'current'
        # CfP is open must not be marked current or done
        assert stages['CFP_OPEN']['phase'] == 'todo'
        # Links in Preparation
        link_titles = [link['title'] for link in stages['PREPARATION']['links']]
        assert 'Configure the event' in link_titles
        assert 'Write a CfP' in link_titles
        assert 'Gather your team' not in link_titles
        assert 'Customize mail templates' not in link_titles
        # Checkbox field present
        assert 'is_configured' in stages['PREPARATION']['links'][0]
        # CFP_OPEN links
        cfp_link_titles = [link['title'] for link in stages['CFP_OPEN']['links']]
        assert 'Add new speaker' in cfp_link_titles
        # Reviewers link points to teams page
        reviewers_link = next(link for link in stages['CFP_OPEN']['links'] if link['title'] == 'Invite reviewers')
        assert reviewers_link['url'] == event.organizer.orga_urls.teams
        # WRAPUP links
        wrapup_titles = [link['title'] for link in stages['WRAPUP']['links']]
        assert 'Release next event date?' not in wrapup_titles

        # Private event with published talks should still have CFP_OPEN as todo
        event.is_public = False
        event.talks_published = True
        event.save()
        assert get_stages(event)['CFP_OPEN']['phase'] == 'todo'

