import pytest
from django_scopes import scope

from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.orga.forms import SubmissionForm


@pytest.mark.django_db
def test_submissionform_content_locale_choices(event):
    event.locale_array = "en,de"
    event.content_locale_array = "en,de,fr"
    event.save()
    with scope(event=event):
        submission_form = SubmissionForm(event)
        assert submission_form.fields["content_locale"].choices == [
            ("en", "English"),
            ("de", "Deutsch"),
            ("fr", "Français"),
        ]


def test_event_common_settings_form_has_separate_header_color_controls():
    assert 'header_background_color' in EventCommonSettingsForm.auto_fields
    assert 'header_text_color' in EventCommonSettingsForm.auto_fields
    assert 'navigation_text_color' in EventCommonSettingsForm.auto_fields
