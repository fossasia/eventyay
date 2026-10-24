import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.cfp.flow import FIELD_DEFAULTS, FIELD_STEP_MAP, CfPFlow, ProfileStep, get_field_default
from eventyay.orga.forms.cfp import CfPBuiltinFieldSettingsForm, CfPSettingsForm


@pytest.fixture(autouse=True)
def _disable_scopes():
    with scopes_disabled():
        yield


def test_field_step_map_and_defaults_coverage():
    """Verify all 22 built-in fields are mapped and have defaults."""
    assert len(FIELD_STEP_MAP) == 22
    fields_without_help_text = {
        'title',
        'submission_type',
        'track',
        'content_locale',
        'slides',
        'do_not_record',
        'fullname',
        'avatar',
        'availabilities',
        'social_links',
    }
    for field_key, step in FIELD_STEP_MAP.items():
        assert step in ('info', 'profile')
        assert field_key in FIELD_DEFAULTS
        assert 'label' in FIELD_DEFAULTS[field_key]
        assert 'help_text' in FIELD_DEFAULTS[field_key]

        label = get_field_default(field_key, 'label', 'en')
        help_text = get_field_default(field_key, 'help_text', 'en')
        assert isinstance(label, str) and len(label) > 0
        assert isinstance(help_text, str)
        if field_key in fields_without_help_text:
            assert help_text == ''
        else:
            assert len(help_text) > 0


def test_builtin_field_settings_form_initial_defaults(event):
    """Verify form initializes with default strings when no custom flow is configured."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='organization')
    assert 'label' in form.fields
    assert 'help_text' in form.fields
    assert 'enable_gravatar' not in form.fields

    default_en_label = get_field_default('organization', 'label', 'en')
    default_en_help = get_field_default('organization', 'help_text', 'en')
    assert form.initial['label'].data['en'] == default_en_label
    assert form.initial['help_text'].data['en'] == default_en_help


def test_builtin_field_settings_form_avatar_gravatar(event):
    """Verify avatar field exposes enable_gravatar and saves it correctly."""
    event.cfp.settings['cfp_enable_gravatar'] = False
    event.cfp.save(update_fields=['settings'])

    form = CfPBuiltinFieldSettingsForm(event=event, field_key='avatar')
    assert 'enable_gravatar' in form.fields
    assert form.initial['enable_gravatar'] is False

    post_data = {
        'label_0': 'Speaker Photo',
        'help_text_0': 'Please upload your photo.',
        'enable_gravatar': True,
    }
    bound_form = CfPBuiltinFieldSettingsForm(event=event, field_key='avatar', data=post_data)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    event.cfp.refresh_from_db()
    assert event.cfp.enable_gravatar is True


def test_builtin_field_settings_form_save_and_editor_sync(event):
    """Verify changes saved in settings form persist to flow config and sync with Editor."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)
    lang_codes = [l[0] for l in settings.LANGUAGES]
    en_idx = lang_codes.index('en')
    de_idx = lang_codes.index('de')
    post_data = {
        f'label_{en_idx}': 'Organization / Company',
        f'label_{de_idx}': 'Organisation / Unternehmen',
        f'help_text_{en_idx}': 'Which company do you represent?',
        f'help_text_{de_idx}': 'Welches Unternehmen vertreten Sie?',
    }
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='organization', data=post_data)
    assert form.is_valid(), form.errors
    form.save()

    flow_config = event.cfp.settings.get('flow')
    assert flow_config is not None
    steps = flow_config.get('steps', {})
    profile_fields = steps.get('profile', {}).get('fields', [])
    org_field = next((f for f in profile_fields if f.get('key') == 'organization'), None)
    assert org_field is not None
    assert org_field['label']['en'] == 'Organization / Company'
    assert org_field['label']['de'] == 'Organisation / Unternehmen'
    assert org_field['help_text']['en'] == 'Which company do you represent?'
    assert org_field['help_text']['de'] == 'Welches Unternehmen vertreten Sie?'

    # Verify synchronization with Editor config
    flow = CfPFlow(event)
    editor_steps = flow.get_editor_config()
    editor_profile_step = next(s for s in editor_steps if s['identifier'] == 'profile')
    editor_org = next((f for f in editor_profile_step['fields'] if f.get('key') == 'organization'), None)
    assert editor_org is not None
    assert editor_org['label'].data['en'] == 'Organization / Company'
    assert editor_org['help_text'].data['en'] == 'Which company do you represent?'


def test_builtin_field_settings_view_get_and_post(organizer_client, event):
    """Verify CfPBuiltinFieldSettings view handles GET, POST save, and 404 for unknown fields."""
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'abstract'},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert 'Field settings:' in response.content.decode()

    # Unknown field raises 404
    bad_url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'nonexistent_field'},
    )
    bad_response = organizer_client.get(bad_url)
    assert bad_response.status_code == 404

    # POST save
    post_data = {
        'label_0': 'Custom Abstract Title',
        'help_text_0': 'Give a short summary of your talk.',
    }
    post_response = organizer_client.post(url, post_data)
    assert post_response.status_code == 302
    assert post_response.url.endswith(url + '?lang=en')

    # Check updated form initial
    get_response = organizer_client.get(url)
    assert get_response.status_code == 200
    assert 'Custom Abstract Title' in get_response.content.decode()


def test_builtin_field_settings_reset_to_default(organizer_client, event):
    """Verify Reset to default removes custom labels and help text so all locales fall back to dynamic translations."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'title'},
    )

    # First, save customized values in both en and de
    lang_codes = [l[0] for l in settings.LANGUAGES]
    en_idx = lang_codes.index('en')
    de_idx = lang_codes.index('de')
    post_data = {
        f'label_{en_idx}': 'Custom Title EN',
        f'label_{de_idx}': 'Custom Title DE',
        f'help_text_{en_idx}': 'Custom Help EN',
        f'help_text_{de_idx}': 'Custom Help DE',
    }
    save_response = organizer_client.post(url, post_data)
    assert save_response.status_code == 302

    # Now post reset
    reset_response = organizer_client.post(url, {'action': 'reset'})
    assert reset_response.status_code == 302

    # Verify custom keys are popped so all locales cleanly fall back to defaults
    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    assert title_field is not None
    assert 'label' not in title_field
    assert 'help_text' not in title_field



def test_forms_overview_renders_settings_links_and_custom_labels(organizer_client, event):
    """Verify Forms overview page renders settings buttons and normal font weight for help text."""
    # Customize a field first
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'notes'},
    )
    post_response = organizer_client.post(url, {
        'label_0': 'Private Notes for Committee',
        'help_text_0': 'Only organizers will see these notes.',
    })
    assert post_response.status_code == 302

    overview_url = reverse(
        'orga:cfp.questions.view',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(overview_url)
    assert response.status_code == 200
    content = response.content.decode()

    # Verify settings link for notes is rendered
    assert url in content
    # Verify custom label and help text are displayed
    assert 'Private Notes for Committee' in content
    assert 'Only organizers will see these notes.' in content
    # Verify floating Gravatar popover is no longer in overview page
    assert 'profile-picture-settings-popover' not in content


def test_cfp_settings_form_does_not_clear_gravatar_when_saved(event):
    """Verify saving CfPSettingsForm without the removed popover does not clear cfp_enable_gravatar."""
    event.cfp.settings['cfp_enable_gravatar'] = True
    event.cfp.save(update_fields=['settings'])
    init_form = CfPSettingsForm(read_only=False, locales=event.locales, obj=event, prefix='settings')
    post_data = {}
    for name, field in init_form.fields.items():
        if name == 'content_locales':
            post_data[f'settings-{name}'] = event.locales
        elif hasattr(field, 'choices'):
            valid_choices = [c[0] for c in field.choices if c[0]]
            fallback_val = valid_choices[0] if valid_choices else ''
            post_data[f'settings-{name}'] = field.initial if field.initial in valid_choices else fallback_val
        elif field.initial is not None:
            post_data[f'settings-{name}'] = field.initial
    sform = CfPSettingsForm(
        read_only=False,
        locales=event.locales,
        obj=event,
        data=post_data,
        prefix='settings',
    )
    assert 'cfp_enable_gravatar' not in sform.fields
    assert sform.is_valid(), sform.errors
    sform.save()
    event.cfp.refresh_from_db()
    assert event.cfp.enable_gravatar is True


def test_profile_step_social_links_context(event, rf):
    """Verify ProfileStep passes configured social_links label and help text to context."""
    event.cfp.settings['flow'] = {
        'steps': {
            'profile': {
                'fields': [
                    {
                        'key': 'social_links',
                        'label': {'en': 'Custom Social Media Heading'},
                        'help_text': {'en': 'Add your LinkedIn or Twitter profile.'},
                    }
                ]
            }
        }
    }
    event.cfp.settings['cfp_request_social_links'] = True
    event.cfp.save(update_fields=['settings'])

    request = rf.get('/cfp/')
    request.user = AnonymousUser()
    request.event = event
    request.LANGUAGE_CODE = 'en'
    step = ProfileStep(event)
    step.request = request
    step.cfp_session = {'data': {}, 'files': {}}

    context = step.get_context_data()
    assert context['social_links_label'] == 'Custom Social Media Heading'
    assert context['social_links_help_text'] == 'Add your LinkedIn or Twitter profile.'


def test_builtin_field_settings_explicitly_empty_help_text_and_disabled_locales(event):
    """Verify empty help text is preserved (not replaced with default) and disabled locales are retained on save."""
    event.locale_array = 'en'
    event.save()
    event.__dict__.pop('locales', None)
    event.cfp.settings['flow'] = {
        'steps': {
            'profile': {
                'fields': [
                    {
                        'key': 'job_title',
                        'label': {'en': 'Job Title EN', 'de': 'Berufsbezeichnung DE'},
                        'help_text': {'en': ''},
                    }
                ]
            }
        }
    }
    event.cfp.save(update_fields=['settings'])

    form = CfPBuiltinFieldSettingsForm(event=event, field_key='job_title')
    assert form.initial['help_text'].data['en'] == ''

    post_data = {
        'label_0': 'Updated Job Title EN',
        'help_text_0': '',
    }
    bound_form = CfPBuiltinFieldSettingsForm(event=event, field_key='job_title', data=post_data)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('profile', {}).get('fields', [])
    job_field = next((f for f in fields if f.get('key') == 'job_title'), None)
    assert job_field is not None
    assert job_field['label']['en'] == 'Updated Job Title EN'
    assert job_field['label']['de'] == 'Berufsbezeichnung DE'
    assert job_field['help_text']['en'] == ''


def test_builtin_field_settings_invalid_active_lang_fallback(organizer_client, event):
    """Verify form_valid falls back to the first available event locale when active_lang is invalid."""
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'title'},
    )
    post_data = {
        'label_0': 'My Proposal Title',
        'help_text_0': 'My Help Text',
        'active_lang': 'invalid_locale_xyz',
    }
    response = organizer_client.post(url, post_data)
    assert response.status_code == 302
    assert response.url.endswith(url + f'?lang={event.locales[0]}')


def test_builtin_field_settings_help_text_sanitized(event):
    """Verify malicious script/handlers in custom help text are sanitized on form save."""
    post_data = {
        'label_0': 'Session Abstract',
        'help_text_0': '<script>alert("xss")</script><p>Safe explanation</p><img src=x onerror=alert(1)>',
    }
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='abstract', data=post_data)
    assert form.is_valid(), form.errors
    form.save()

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    abstract_field = next((f for f in fields if f.get('key') == 'abstract'), None)
    assert abstract_field is not None
    saved_help = abstract_field['help_text']['en']
    assert '<script>' not in saved_help
    assert 'onerror' not in saved_help
    assert 'Safe explanation' in saved_help


def test_profile_step_social_links_help_text_sanitized(event, rf):
    """Verify ProfileStep sanitizes malicious script in social links help text."""
    event.__dict__.pop('cfp_flow', None)
    event.cfp.settings['flow'] = {
        'steps': {
            'profile': {
                'fields': [
                    {
                        'key': 'social_links',
                        'label': {'en': 'Socials'},
                        'help_text': {'en': '<script>alert("pwned")</script>Connect with us'},
                    }
                ]
            }
        }
    }
    event.cfp.settings['cfp_request_social_links'] = True
    event.cfp.save(update_fields=['settings'])

    request = rf.get('/cfp/')
    request.user = AnonymousUser()
    request.event = event
    request.LANGUAGE_CODE = 'en'
    step = ProfileStep(event)
    step.request = request
    step.cfp_session = {'data': {}, 'files': {}}
    context = step.get_context_data()
    assert '<script>' not in context['social_links_help_text']
    assert 'Connect with us' in context['social_links_help_text']


def test_builtin_field_settings_dict_fields_mapping_keys_preserved(event):
    """Verify steps using dict mapping for fields retain existing field settings on save and reset."""
    event.cfp.settings['flow'] = {
        'steps': {
            'info': {
                'fields': {
                    'title': {'label': {'en': 'Existing Title'}, 'request': 'required'},
                    'abstract': {'label': {'en': 'Existing Abstract'}, 'request': 'optional'},
                }
            }
        }
    }
    event.cfp.save(update_fields=['settings'])

    post_data = {
        'label_0': 'Brand New Title',
        'help_text_0': 'Title help',
    }
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='title', data=post_data)
    assert form.is_valid(), form.errors
    form.save()

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    # Verify abstract field is NOT lost
    abstract_field = next((f for f in fields if f.get('key') == 'abstract'), None)
    assert abstract_field is not None
    assert abstract_field['label']['en'] == 'Existing Abstract'

    # Verify title was updated
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    assert title_field is not None
    assert title_field['label']['en'] == 'Brand New Title'


def test_builtin_field_settings_identical_translations_preserved(event):
    """Verify intentionally identical translations across locales are preserved and not overwritten with gettext."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)

    lang_codes = [l[0] for l in settings.LANGUAGES]
    en_idx = lang_codes.index('en')
    de_idx = lang_codes.index('de')

    post_data = {
        f'label_{en_idx}': 'Topic area',
        f'label_{de_idx}': 'Topic area',
        f'help_text_{en_idx}': 'Choose your track',
        f'help_text_{de_idx}': 'Choose your track',
    }
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='track', data=post_data)
    assert form.is_valid(), form.errors
    form.save()

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    track_field = next((f for f in fields if f.get('key') == 'track'), None)
    assert track_field is not None
    assert track_field['label']['en'] == 'Topic area'
    assert track_field['label']['de'] == 'Topic area'
    assert track_field['help_text']['en'] == 'Choose your track'
    assert track_field['help_text']['de'] == 'Choose your track'


def test_builtin_field_settings_avatar_gravatar_atomic_save(event, monkeypatch):
    """Verify avatar flow config and gravatar setting are committed atomically."""
    event.cfp.settings['cfp_enable_gravatar'] = False
    event.cfp.save(update_fields=['settings'])

    post_data = {
        'label_0': 'My Avatar',
        'help_text_0': 'Upload avatar',
        'enable_gravatar': True,
    }
    form = CfPBuiltinFieldSettingsForm(event=event, field_key='avatar', data=post_data)
    assert form.is_valid()

    def failing_save_config(*args, **kwargs):
        raise RuntimeError('Simulated database write failure')

    monkeypatch.setattr(CfPFlow, 'save_config', failing_save_config)
    with pytest.raises(RuntimeError):
        form.save()

    event.cfp.refresh_from_db()
    assert event.cfp.enable_gravatar is False


def test_builtin_field_settings_reset_to_default_without_active_lang(organizer_client, event):
    """Verify reset clears custom label and help_text from flow config and falls back to dynamic defaults."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'title'},
    )

    lang_codes = [l[0] for l in settings.LANGUAGES]
    en_idx = lang_codes.index('en')
    de_idx = lang_codes.index('de')
    post_data = {
        f'label_{en_idx}': 'Custom Title EN',
        f'label_{de_idx}': 'Custom Title DE',
        f'help_text_{en_idx}': 'Custom Help EN',
        f'help_text_{de_idx}': 'Custom Help DE',
    }
    organizer_client.post(url, post_data)

    reset_response = organizer_client.post(url, {'action': 'reset'})
    assert reset_response.status_code == 302

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    assert title_field is not None
    assert 'label' not in title_field
    assert 'help_text' not in title_field

    # Verify form reopens with platform defaults for all locales
    get_response = organizer_client.get(url)
    assert get_response.status_code == 200
    form = get_response.context['form']
    assert form.initial['label'].data['en'] == get_field_default('title', 'label', 'en')
    assert form.initial['label'].data['de'] == get_field_default('title', 'label', 'de')


def test_builtin_field_settings_template_stacked_locales_and_active_lang(organizer_client, event):
    """Verify multilingual event renders all language inputs stacked simultaneously."""
    event.locale_array = 'en,de'
    event.save()
    event.__dict__.pop('locales', None)
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'title'},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # Form renders both locale inputs simultaneously
    assert 'lang="en"' in content
    assert 'lang="de"' in content
    assert 'name="active_lang"' in content
    assert 'id="active_lang"' in content


def test_builtin_field_settings_non_english_fallback_locale(organizer_client, event):
    """Verify event configured only in German clears custom keys on reset and defaults cleanly."""
    event.locale_array = 'de'
    event.save()
    event.__dict__.pop('locales', None)
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'title'},
    )
    de_idx = [l[0] for l in settings.LANGUAGES].index('de')
    organizer_client.post(url, {f'label_{de_idx}': 'Eigener Titel DE', f'help_text_{de_idx}': ''})

    response = organizer_client.post(url, {'action': 'reset'})
    assert response.status_code == 302

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    assert title_field is not None
    assert 'label' not in title_field
    assert 'help_text' not in title_field


def test_builtin_field_settings_audit_logging_on_save_and_reset(organizer_client, event):
    """Verify saving or resetting field settings logs eventyay.cfp.update action."""
    url = reverse(
        'orga:cfp.field.settings',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'field': 'notes'},
    )
    initial_log_count = event.cfp.logged_actions().filter(action_type='eventyay.cfp.update').count()

    # Save
    save_response = organizer_client.post(url, {'label_0': 'New Notes', 'help_text_0': 'New Notes Help'})
    assert save_response.status_code == 302
    assert event.cfp.logged_actions().filter(action_type='eventyay.cfp.update').count() == initial_log_count + 1
    last_log = event.cfp.logged_actions().filter(action_type='eventyay.cfp.update').order_by('-id').first()
    assert last_log.parsed_data.get('field') == 'notes'

    # Reset
    reset_response = organizer_client.post(url, {'action': 'reset'})
    assert reset_response.status_code == 302
    assert event.cfp.logged_actions().filter(action_type='eventyay.cfp.update').count() == initial_log_count + 2
    last_log = event.cfp.logged_actions().filter(action_type='eventyay.cfp.update').order_by('-id').first()
    assert last_log.parsed_data.get('field') == 'notes'
    assert last_log.parsed_data.get('action') == 'reset'


def test_speaker_social_links_template_renders_html_unescaped(rf, event):
    """Verify speaker_social_links_formset.html renders sanitized HTML in social_links_help_text unescaped."""
    from eventyay.person.forms import build_speaker_social_links_formset

    formset = build_speaker_social_links_formset()
    html = render_to_string(
        'common/speaker_social_links_formset.html',
        {
            'social_media_formset': formset,
            'social_links_label': 'Socials',
            'social_links_help_text': '<a href="https://example.com">Visit our site</a>',
            'request': rf.get('/'),
        },
    )
    assert '<a href="https://example.com">Visit our site</a>' in html
    assert '&lt;a href=' not in html


def test_builtin_field_settings_unchanged_defaults_not_stored(event):
    """Verify saving field settings with unchanged default label and help text does not store them in flow config."""
    event.locale_array = 'en'
    event.save()
    event.__dict__.pop('locales', None)

    default_label = get_field_default('title', 'label', 'en')
    default_help = get_field_default('title', 'help_text', 'en')

    form = CfPBuiltinFieldSettingsForm(
        event=event,
        field_key='title',
        data={'label_0': default_label, 'help_text_0': default_help},
    )
    assert form.is_valid(), form.errors
    form.save()

    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    if title_field:
        assert 'label' not in title_field
        assert 'help_text' not in title_field



