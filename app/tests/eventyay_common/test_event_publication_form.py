import pytest

from eventyay.eventyay_common.forms.event import EventPublicationForm


@pytest.mark.django_db
def test_event_publication_form_persists_display_settings(event):
    form = EventPublicationForm(
        data={
            'meta_noindex': True,
            'exclude_from_start_page': True,
        },
        obj=event,
    )
    assert form.is_valid(), form.errors
    form.save()
    event.refresh_from_db()
    assert event.display_settings['meta_noindex'] is True
    assert event.display_settings['exclude_from_start_page'] is True


@pytest.mark.django_db
def test_event_publication_form_clears_boolean_flags(event):
    event.display_settings = {
        **(event.display_settings or {}),
        'meta_noindex': True,
        'exclude_from_start_page': True,
    }
    event.save(update_fields=['display_settings'])

    form = EventPublicationForm(
        data={
            'meta_noindex': False,
            'exclude_from_start_page': False,
        },
        obj=event,
    )
    assert form.is_valid(), form.errors
    form.save()
    event.refresh_from_db()
    assert event.display_settings['meta_noindex'] is False
    assert event.display_settings['exclude_from_start_page'] is False


@pytest.mark.django_db
def test_event_publication_form_does_not_mutate_shared_display_settings(event):
    shared = {'schedule': 'grid'}
    event.display_settings = shared
    event.save(update_fields=['display_settings'])

    form = EventPublicationForm(
        data={
            'meta_noindex': False,
            'exclude_from_start_page': False,
        },
        obj=event,
    )
    assert form.is_valid(), form.errors
    form.save()

    assert shared == {'schedule': 'grid'}
    event.refresh_from_db()
    assert event.display_settings['exclude_from_start_page'] is False
