import pytest
from django.conf import settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.cfp.flow import FIELD_DEFAULTS, FIELD_STEP_MAP, CfPFlow, get_field_default
from eventyay.orga.forms.cfp import CfPBuiltinFieldSettingsForm, CfPSettingsForm


@pytest.fixture(autouse=True)
def _disable_scopes():
    with scopes_disabled():
        yield


def test_field_step_map_and_defaults_coverage():
    """Verify all 22 built-in fields are mapped and have defaults."""
    assert len(FIELD_STEP_MAP) == 22
    for field_key, step in FIELD_STEP_MAP.items():
        assert step in ('info', 'profile')
        assert field_key in FIELD_DEFAULTS
        assert 'label' in FIELD_DEFAULTS[field_key]
        assert 'help_text' in FIELD_DEFAULTS[field_key]

        label = get_field_default(field_key, 'label', 'en')
        help_text = get_field_default(field_key, 'help_text', 'en')
        assert isinstance(label, str) and len(label) > 0
        assert isinstance(help_text, str) and len(help_text) > 0


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
    """Verify Reset to default restores defaults for the active language while preserving other languages."""
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

    # Now post reset for English only
    reset_response = organizer_client.post(url, {'action': 'reset', 'active_lang': 'en'})
    assert reset_response.status_code == 302

    # Verify English was reset to platform default, but German was kept custom
    event.cfp.refresh_from_db()
    flow_config = event.cfp.settings.get('flow', {})
    fields = flow_config.get('steps', {}).get('info', {}).get('fields', [])
    title_field = next((f for f in fields if f.get('key') == 'title'), None)
    assert title_field is not None

    default_en_label = get_field_default('title', 'label', 'en')
    default_en_help = get_field_default('title', 'help_text', 'en')
    assert title_field['label']['en'] == default_en_label
    assert title_field['help_text']['en'] == default_en_help
    assert title_field['label']['de'] == 'Custom Title DE'
    assert title_field['help_text']['de'] == 'Custom Help DE'


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
    sform = CfPSettingsForm(
        read_only=False,
        locales=event.locales,
        obj=event,
        data={
            'settings-cfp_ask_title': 'required',
            'settings-cfp_ask_abstract': 'optional',
        },
        prefix='settings',
    )
    assert 'cfp_enable_gravatar' not in sform.fields
    if sform.is_valid():
        sform.save()
    event.cfp.refresh_from_db()
    assert event.cfp.enable_gravatar is True
