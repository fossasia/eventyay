import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import SubmissionStates
from eventyay.event.stages import get_workflow_steps


@pytest.mark.django_db
def test_workflow_steps_structure(event):
    with scope(event=event):
        steps = get_workflow_steps(event)
        assert len(steps) == 7
        labels = [s['label'] for s in steps]
        assert 'Call for proposals' in labels
        assert 'Review' in labels
        assert 'Acceptance' in labels
        assert 'Confirmation' in labels
        assert 'Scheduling' in labels
        assert 'Published' in labels
        assert 'Live' in labels
        for step in steps:
            assert 'phase' in step
            assert 'status' in step
            assert 'summary' in step
            assert 'icon' in step


@pytest.mark.django_db
def test_dashboard_context_sections(event, orga_client, accepted_submission, slot):
    with scope(event=event):
        response = orga_client.get(event.orga_urls.base)
        assert response.status_code == 200

        # Verify new context variables
        ctx = response.context
        assert 'workflow_steps' in ctx
        assert 'action_items' in ctx
        assert 'kpi_cards' in ctx
        assert 'session_readiness' in ctx
        assert 'speaker_readiness' in ctx
        assert 'internal_note' in ctx

        # Check KPI card metrics
        kpi_labels = [c['label'] for c in ctx['kpi_cards']]
        assert 'Submitted proposals' in kpi_labels
        assert 'Accepted proposals' in kpi_labels
        assert 'Confirmed sessions' in kpi_labels
        assert 'Scheduled sessions' in kpi_labels
        assert 'Speakers' in kpi_labels

        # Check readiness lists
        assert len(ctx['session_readiness']) >= 3
        assert len(ctx['speaker_readiness']) >= 3


@pytest.mark.django_db
def test_dashboard_action_items_unconfirmed(event, orga_client, accepted_submission):
    with scope(event=event):
        response = orga_client.get(event.orga_urls.base)
        assert response.status_code == 200
        action_titles = [item['title'] for item in response.context['action_items']]
        assert 'Unconfirmed sessions' in action_titles


@pytest.mark.django_db
def test_dashboard_save_internal_note(event, orga_client):
    with scope(event=event):
        url = event.orga_urls.base + 'note/'
        post_data = {'note': 'Meeting with keynote speakers on Monday.'}
        response = orga_client.post(url, data=post_data)
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        event.settings.flush()
        assert event.settings.get('dashboard_internal_note') == 'Meeting with keynote speakers on Monday.'


@pytest.mark.django_db
def test_dashboard_template_renders_sections(event, orga_client, accepted_submission):
    with scope(event=event):
        response = orga_client.get(event.orga_urls.base)
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Talk workflow' in content
        assert 'At a glance' in content
        assert 'Session readiness' in content
        assert 'Speaker readiness' in content
        assert 'Internal note' in content
