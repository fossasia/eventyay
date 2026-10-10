import json

import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.cfp.flow import CfPFlow
from eventyay.common.language import language
from eventyay.orga.forms.cfp import (
    BUILTIN_FIELD_DEFAULTS,
    CfPFieldSettingsForm,
)
from eventyay.person.forms import SpeakerProfileForm
from eventyay.submission.forms import InfoForm


@pytest.mark.django_db
def test_preserve_existing_flow_as_json_string(event):
    """Test finding 1: Detect and decode JSON string flow, preserving other steps and fields."""
    with scope(event=event):
        existing_flow = {
            'metadata': {'version': 1, 'author': 'tester'},
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {'key': 'description', 'label': {'en': 'Custom Desc'}, 'help_text': {'en': 'Help text'}},
                    ],
                },
                'custom_step': {
                    'identifier': 'custom_step',
                    'fields': [{'key': 'custom_field', 'label': {'en': 'Custom Step Label'}}],
                },
            },
        }
        event.cfp.settings['flow'] = json.dumps(existing_flow)
        event.cfp.save(update_fields=['settings'])

        # Save title setting on 'info' step
        form = CfPFieldSettingsForm(
            data={'label_0': 'My Custom Title', 'help_text_0': 'Enter title here'},
            event=event,
            target='session',
            field_id='title',
        )
        assert form.is_valid(), form.errors
        form.save()
        event.refresh_from_db()

        saved_flow = event.cfp.settings['flow']
        assert isinstance(saved_flow, dict)
        assert saved_flow['metadata'] == {'version': 1, 'author': 'tester'}
        assert 'custom_step' in saved_flow['steps']
        assert saved_flow['steps']['custom_step']['fields'][0]['key'] == 'custom_field'

        info_fields = {f['key']: f for f in saved_flow['steps']['info']['fields']}
        assert 'description' in info_fields
        assert info_fields['description']['label'] == {'en': 'Custom Desc'}
        assert 'title' in info_fields
        assert info_fields['title']['label']['en'] == 'My Custom Title'


@pytest.mark.django_db
def test_reset_field_preserves_json_string_flow(event):
    """Test finding 1: Resetting one field preserves other steps and fields when stored as JSON string."""
    with scope(event=event):
        existing_flow = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {'key': 'title', 'label': {'en': 'Custom Title'}},
                        {'key': 'description', 'label': {'en': 'Custom Description'}},
                    ],
                },
            },
        }
        event.cfp.settings['flow'] = json.dumps(existing_flow)
        event.cfp.save(update_fields=['settings'])

        form = CfPFieldSettingsForm(
            event=event,
            target='session',
            field_id='title',
        )
        form.reset_locale('en')
        event.refresh_from_db()

        saved_flow = event.cfp.settings['flow']
        assert isinstance(saved_flow, dict)
        info_fields = {f['key']: f for f in saved_flow['steps']['info']['fields']}
        assert 'description' in info_fields
        assert info_fields['description']['label'] == {'en': 'Custom Description'}
        assert 'title' in info_fields
        default_title = str(BUILTIN_FIELD_DEFAULTS['session']['title']['label'])
        assert info_fields['title']['label']['en'] == default_title


@pytest.mark.django_db
def test_safe_handling_of_malformed_json_flow(event):
    """Test finding 1: Malformed JSON string is safely handled without raising an unhandled error."""
    with scope(event=event):
        event.cfp.settings['flow'] = '{"steps": invalid json'
        event.cfp.save(update_fields=['settings'])

        form = CfPFieldSettingsForm(
            data={'label_0': 'My Proposal Title', 'help_text_0': ''},
            event=event,
            target='session',
            field_id='title',
        )
        assert form.is_valid(), form.errors
        form.save()
        event.refresh_from_db()

        saved_flow = event.cfp.settings['flow']
        assert isinstance(saved_flow, dict)
        assert 'steps' in saved_flow
        assert 'info' in saved_flow['steps']
        info_fields = {f['key']: f for f in saved_flow['steps']['info']['fields']}
        assert info_fields['title']['label']['en'] == 'My Proposal Title'


@pytest.mark.django_db
def test_preserve_inactive_locales_on_save_and_reset(event):
    """Test finding 2: Translations for inactive/removed locales survive saving and resetting active locales."""
    with scope(event=event):
        # Event has only 'en' active, but French and German were previously stored
        event.locale_array = 'en'
        event.settings.set('locales', ['en'])
        event.save()

        flow_data = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {
                            'key': 'title',
                            'label': {
                                'en': 'English Title',
                                'de': 'Deutscher Titel',
                                'fr': 'Titre Français',
                            },
                            'help_text': {
                                'en': 'English Help',
                                'de': 'Deutsche Hilfe',
                                'fr': 'Aide Française',
                            },
                        }
                    ],
                }
            }
        }
        event.cfp.settings['flow'] = flow_data
        event.cfp.save(update_fields=['settings'])

        # 1. Save new English translation
        form = CfPFieldSettingsForm(
            data={
                'label_0': 'Updated English Title',
                'help_text_0': 'Updated English Help',
            },
            event=event,
            target='session',
            field_id='title',
        )
        assert form.is_valid(), form.errors
        form.save()
        event.refresh_from_db()

        field_config = event.cfp.settings['flow']['steps']['info']['fields'][0]
        # Inactive locales must still be present
        assert field_config['label']['de'] == 'Deutscher Titel'
        assert field_config['label']['fr'] == 'Titre Français'
        assert field_config['label']['en'] == 'Updated English Title'
        assert field_config['help_text']['de'] == 'Deutsche Hilfe'
        assert field_config['help_text']['fr'] == 'Aide Française'
        assert field_config['help_text']['en'] == 'Updated English Help'

        # 2. Reset English locale
        form = CfPFieldSettingsForm(
            event=event,
            target='session',
            field_id='title',
        )
        form.reset_locale('en')
        event.refresh_from_db()

        field_config = event.cfp.settings['flow']['steps']['info']['fields'][0]
        default_title = str(BUILTIN_FIELD_DEFAULTS['session']['title']['label'])
        assert field_config['label']['en'] == default_title
        # Inactive locales still survive the reset!
        assert field_config['label']['de'] == 'Deutscher Titel'
        assert field_config['label']['fr'] == 'Titre Français'
        assert field_config['help_text']['de'] == 'Deutsche Hilfe'
        assert field_config['help_text']['fr'] == 'Aide Française'


@pytest.mark.django_db
def test_customized_field_labels_and_help_text_on_public_form(event):
    """Test finding 3: Configured labels and help text appear on public proposal forms."""
    with scope(event=event):
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {
                            'key': 'title',
                            'label': {'en': 'Custom Presentation Title'},
                            'help_text': {'en': 'Custom Title Help Text'},
                        },
                    ],
                },
                'profile': {
                    'identifier': 'profile',
                    'fields': [
                        {
                            'key': 'avatar',
                            'label': {'en': 'Speaker Headshot'},
                            'help_text': {'en': 'Upload your headshot here.'},
                        },
                        {
                            'key': 'social_links',
                            'label': {'en': 'Online Profiles'},
                            'help_text': {'en': 'Add your GitHub or Mastodon profile.'},
                        },
                    ],
                },
            }
        }
        event.cfp.fields['social_links'] = {'visibility': 'optional'}
        event.cfp.save(update_fields=['settings', 'fields'])
        event.__dict__.pop('cfp_flow', None)

        flow = CfPFlow(event)
        info_step_config = flow.config['steps']['info']['fields']
        profile_step_config = flow.config['steps']['profile']['fields']

        # 1. InfoForm reflects customized title label and help text
        info_form = InfoForm(event=event, field_configuration=info_step_config)
        assert str(info_form.fields['title'].label) == 'Custom Presentation Title'
        assert 'Custom Title Help Text' in str(info_form.fields['title'].help_text)

        # 2. SpeakerProfileForm reflects customized avatar and social_links
        profile_form = SpeakerProfileForm(
            event=event,
            field_configuration=profile_step_config,
        )
        assert str(profile_form.fields['avatar'].label) == 'Speaker Headshot'
        assert 'Upload your headshot here.' in str(profile_form.fields['avatar'].help_text)
        assert 'social_links' in profile_form.fields
        assert str(profile_form.fields['social_links'].label) == 'Online Profiles'
        assert 'Add your GitHub or Mastodon profile.' in str(profile_form.fields['social_links'].help_text)


@pytest.mark.django_db
def test_default_labels_and_help_text_when_no_customization(event):
    """Test finding 3: Default labels remain unchanged when no customization exists."""
    with scope(event=event):
        event.cfp.settings['flow'] = {}
        event.cfp.fields['social_links'] = {'visibility': 'optional'}
        event.cfp.save(update_fields=['settings', 'fields'])
        event.__dict__.pop('cfp_flow', None)

        flow = CfPFlow(event)
        info_step_config = flow.config.get('steps', {}).get('info', {}).get('fields')
        profile_step_config = flow.config.get('steps', {}).get('profile', {}).get('fields')

        info_form = InfoForm(event=event, field_configuration=info_step_config)
        default_title = str(BUILTIN_FIELD_DEFAULTS['session']['title']['label'])
        assert str(info_form.fields['title'].label) == default_title

        profile_form = SpeakerProfileForm(event=event, field_configuration=profile_step_config)
        default_avatar = str(BUILTIN_FIELD_DEFAULTS['speaker']['avatar']['label'])
        assert str(profile_form.fields['avatar'].label) == default_avatar
        assert str(profile_form.fields['social_links'].label) == 'Social Media'


@pytest.mark.django_db
def test_explicitly_cleared_help_text_remains_empty_in_forms_overview(orga_client, event):
    """Test finding 5: Untouched field shows default help text, cleared help text shows empty."""
    with scope(event=event):
        # 1. Untouched field
        event.cfp.settings['flow'] = {}
        event.cfp.save(update_fields=['settings'])
        event.__dict__.pop('cfp_flow', None)

        response = orga_client.get(
            reverse('orga:cfp.forms', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
        )
        assert response.status_code == 200
        # Default help text for abstract exists in context
        assert response.context['question_help_texts'].get('abstract')

        # 2. Explicitly clear help text for abstract
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {'key': 'abstract', 'label': {'en': 'Abstract'}, 'help_text': {'en': ''}},
                    ],
                }
            }
        }
        event.cfp.save(update_fields=['settings'])
        event.__dict__.pop('cfp_flow', None)

        response = orga_client.get(
            reverse('orga:cfp.forms', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
        )
        assert response.status_code == 200
        # Cleared help text must be empty string in question_help_texts
        assert response.context['question_help_texts'].get('abstract') == ''

        # 3. Customized help text
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {'key': 'abstract', 'label': {'en': 'Abstract'}, 'help_text': {'en': 'Custom abstract help'}},
                    ],
                }
            }
        }
        event.cfp.save(update_fields=['settings'])
        event.__dict__.pop('cfp_flow', None)

        response = orga_client.get(
            reverse('orga:cfp.forms', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
        )
        assert response.status_code == 200
        assert response.context['question_help_texts'].get('abstract') == 'Custom abstract help'


@pytest.mark.django_db
def test_session_videos_field_settings_not_exposed(orga_client, event):
    """Test finding 6: session_videos does not expose Field Settings and returns 404 if accessed."""
    with scope(event=event):
        url = reverse(
            'orga:cfp.forms.field_settings',
            kwargs={
                'organizer': event.organizer.slug,
                'event': event.slug,
                'target': 'session',
                'field': 'session_videos',
            },
        )
        response = orga_client.get(url)
        assert response.status_code == 404

        # Forms overview does not have a Settings gear button for session_videos
        overview_url = reverse(
            'orga:cfp.forms',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        response = orga_client.get(overview_url)
        assert response.status_code == 200
        assert url not in response.rendered_content

        # Content Locale has exactly one Settings icon and no duplicate button
        content = response.rendered_content
        assert 'content-locale-settings-btn' not in content
        content_locale_url = reverse(
            'orga:cfp.forms.field_settings',
            kwargs={
                'organizer': event.organizer.slug,
                'event': event.slug,
                'target': 'session',
                'field': 'content_locale',
            },
        )
        assert content.count(f'href="{content_locale_url}"') == 1


@pytest.mark.django_db
def test_cfp_field_settings_post_reset_csp_compatible(orga_client, event):
    """Test that resetting a locale via action='reset:<locale>' works and template contains no inline JS."""
    with scope(event=event):
        event.locale_array = 'en,de'
        event.settings.set('locales', ['en', 'de'])
        event.save()

        # Seed custom labels for both en and de
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {
                            'key': 'title',
                            'label': {'en': 'Custom English Title', 'de': 'Custom German Title'},
                            'help_text': {'en': 'Help EN', 'de': 'Help DE'},
                        }
                    ],
                }
            }
        }
        event.cfp.save(update_fields=['settings'])

        url = reverse(
            'orga:cfp.forms.field_settings',
            kwargs={
                'organizer': event.organizer.slug,
                'event': event.slug,
                'target': 'session',
                'field': 'title',
            },
        )

        # 1. Verify GET renders dropdown without inline onclick handlers
        get_response = orga_client.get(url)
        assert get_response.status_code == 200
        content = get_response.rendered_content
        assert 'onclick=' not in content
        assert 'reset-locale-input' not in content
        assert 'name="action" value="reset:de"' in content
        assert 'name="action" value="reset:en"' in content

        # 2. Reset German locale via action='reset:de'
        post_response = orga_client.post(url, {'action': 'reset:de'})
        assert post_response.status_code == 302

        event.refresh_from_db()
        field_config = event.cfp.settings['flow']['steps']['info']['fields'][0]

        # English customization is preserved
        assert field_config['label']['en'] == 'Custom English Title'
        assert field_config['help_text']['en'] == 'Help EN'

        # German is reset to default (e.g. 'Titel' in German)
        assert field_config['label']['de'] != 'Custom German Title'
        assert field_config['label']['de'] == 'Titel'


@pytest.mark.django_db
def test_reset_only_selected_locale_persisted(event):
    """Test requirement A: Resetting one locale persists ONLY the selected locale."""
    with scope(event=event):
        event.locale_array = 'en,de'
        event.settings.set('locales', ['en', 'de'])
        event.save()

        # No custom stored values initially
        event.cfp.settings['flow'] = {}
        event.cfp.save(update_fields=['settings'])

        form = CfPFieldSettingsForm(
            event=event,
            target='session',
            field_id='title',
        )
        form.reset_locale('de')
        event.refresh_from_db()

        saved_flow = event.cfp.settings['flow']
        assert isinstance(saved_flow, dict)
        info_fields = {f['key']: f for f in saved_flow['steps']['info']['fields']}
        assert 'title' in info_fields
        title_config = info_fields['title']

        # ONLY 'de' must be persisted; 'en' must NOT be automatically persisted
        assert 'de' in title_config['label']
        assert 'en' not in title_config['label']
        assert title_config['label'] == {'de': 'Titel'}

        assert 'de' in title_config['help_text']
        assert 'en' not in title_config['help_text']
        assert title_config['help_text'] == {'de': ''}


@pytest.mark.django_db
def test_missing_locale_uses_builtin_fallback(event):
    """Test requirement B: Missing locale uses built-in default at runtime, not another locale."""
    with scope(event=event):
        event.locale_array = 'en,de'
        event.settings.set('locales', ['en', 'de'])
        event.save()

        # Stored value only contains 'de'
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {
                            'key': 'title',
                            'label': {'de': 'Deutscher Einreichungstitel'},
                        },
                        {
                            'key': 'abstract',
                            'help_text': {'de': 'Eigener deutscher Hilfetext'},
                        },
                    ],
                }
            }
        }
        event.cfp.save(update_fields=['settings'])
        event.__dict__.pop('cfp_flow', None)

        flow = CfPFlow(event)
        info_fields = {f['key']: f for f in flow.config['steps']['info']['fields']}

        # 1. Flow config resolution: requesting English must NOT return the German value
        with language('en'):
            assert str(info_fields['title']['label']) == 'Proposal title'
            assert str(info_fields['title']['label']) != 'Deutscher Einreichungstitel'
            # abstract has a built-in markdown help text in English
            assert 'Markdown' in str(info_fields['abstract']['help_text'])
            assert str(info_fields['abstract']['help_text']) != 'Eigener deutscher Hilfetext'

        # 2. Flow config resolution: requesting German returns the German custom value
        with language('de'):
            assert str(info_fields['title']['label']) == 'Deutscher Einreichungstitel'
            assert str(info_fields['abstract']['help_text']) == 'Eigener deutscher Hilfetext'

        # 3. Form field resolution: InfoForm reflects built-in defaults for missing English
        with language('en'):
            info_form_en = InfoForm(event=event, field_configuration=flow.config['steps']['info']['fields'])
            assert str(info_form_en.fields['title'].label) == 'Proposal title'
            assert str(info_form_en.fields['title'].label) != 'Deutscher Einreichungstitel'
            assert 'Markdown' in str(info_form_en.fields['abstract'].help_text)
            assert 'Eigener deutscher Hilfetext' not in str(info_form_en.fields['abstract'].help_text)

        with language('de'):
            info_form_de = InfoForm(event=event, field_configuration=flow.config['steps']['info']['fields'])
            assert str(info_form_de.fields['title'].label) == 'Deutscher Einreichungstitel'
            assert 'Eigener deutscher Hilfetext' in str(info_form_de.fields['abstract'].help_text)


@pytest.mark.django_db
def test_existing_custom_translations_preserved_on_reset(event):
    """Test requirement C & D: Existing custom translations in other locales remain untouched."""
    with scope(event=event):
        event.locale_array = 'en,de'
        event.settings.set('locales', ['en', 'de'])
        event.save()

        # Custom translations stored for both en and de
        event.cfp.settings['flow'] = {
            'steps': {
                'info': {
                    'identifier': 'info',
                    'fields': [
                        {
                            'key': 'title',
                            'label': {'en': 'Custom English Title', 'de': 'Custom German Title'},
                            'help_text': {'en': 'Custom English Help', 'de': 'Custom German Help'},
                        }
                    ],
                }
            }
        }
        event.cfp.save(update_fields=['settings'])

        form = CfPFieldSettingsForm(
            event=event,
            target='session',
            field_id='title',
        )
        form.reset_locale('de')
        event.refresh_from_db()

        field_config = event.cfp.settings['flow']['steps']['info']['fields'][0]

        # English custom values remain untouched
        assert field_config['label']['en'] == 'Custom English Title'
        assert field_config['help_text']['en'] == 'Custom English Help'

        # German values are reset to built-in defaults
        assert field_config['label']['de'] == 'Titel'
        assert field_config['help_text']['de'] == ''
