import functools
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.global_plugin_config import GlobalPluginConfig
from eventyay.base.models.mail import MailTemplateRoles
from eventyay.control.signals import platform_mail_templates
from eventyay.control.views.admin_messages import (
    PLACEHOLDER_PATTERN,
    get_platform_mail_templates,
    text_to_editor_html,
)


@pytest.fixture
def admin_client(client, db):
    admin = User.objects.create_adminuser(email='admin@example.com', password='admin-pass')
    client.force_login(admin)
    session = client.session
    session.save()
    StaffSession.objects.create(user=admin, session_key=session.session_key)
    return client


@pytest.mark.django_db
def test_every_template_has_content():
    for template in get_platform_mail_templates():
        subject, body = template['load']()
        assert subject.strip(), template['key']
        assert body.strip(), template['key']


@pytest.mark.django_db
def test_templates_without_content_are_not_listed():
    names = {str(template['name']) for template in get_platform_mail_templates()}
    for name in (
        'Billing validation',
        'Refund notification',
        'Reviewer notification',
        'Team member notification',
        'Video/event notification',
    ):
        assert name not in names


@pytest.mark.django_db
def test_every_template_key_is_listed_once():
    keys = [template['key'] for template in get_platform_mail_templates()]
    assert len(keys) == len(set(keys))


@pytest.mark.django_db
def test_organiser_invitation_covers_new_and_registered_users():
    templates = {template['key']: template for template in get_platform_mail_templates()}
    _, invitation = templates['organiser-invitation']['load']()
    _, added = templates['organiser-added-to-team']['load']()
    assert 'You have been invited to the following event team' in invitation
    assert 'You have been added to the following event team' in added


def test_text_to_editor_html_keeps_paragraphs_and_placeholders():
    html = text_to_editor_html('Hello {name},\nsee <this>\n\nBye {event}')
    assert html == (
        '<p>Hello <span data-variable="name">{name}</span>,<br>see &lt;this&gt;</p>'
        '<p>Bye <span data-variable="event">{event}</span></p>'
    )


@pytest.mark.django_db
def test_template_list_links_every_template(admin_client):
    response = admin_client.get(reverse('eventyay_admin:admin.messages.templates'))
    assert response.status_code == 200
    content = response.content.decode()
    for template in get_platform_mail_templates():
        url = template.get('url') or reverse(
            'eventyay_admin:admin.messages.template_detail', kwargs={'role': template['key']}
        )
        assert url in content


@pytest.mark.django_db
def test_plugin_template_links_to_customization_page(admin_client):
    def plugin_templates(sender, **kwargs):
        return {
            'key': 'plugin-billing-notice',
            'name': 'Plugin billing notice',
            'category': 'Business',
            'trigger': 'Invoice issued',
            'load': lambda: ('Invoice {number}', 'Invoice {number} is ready.'),
            'url': '/admin/plugin/billing-template/',
        }

    platform_mail_templates.connect(
        plugin_templates,
        dispatch_uid='test_plugin_template_links_to_customization_page',
    )
    try:
        response = admin_client.get(reverse('eventyay_admin:admin.messages.templates'))
    finally:
        platform_mail_templates.disconnect(dispatch_uid='test_plugin_template_links_to_customization_page')

    assert response.status_code == 200
    assert 'Plugin billing notice' in response.content.decode()
    assert 'Business' in response.content.decode()
    assert "href='/admin/plugin/billing-template/'" in response.content.decode()


@pytest.mark.django_db
def test_plugin_template_registry_isolates_invalid_receivers(admin_client):
    def broken_receiver(sender, **kwargs):
        raise RuntimeError('broken plugin')

    def invalid_templates(sender, **kwargs):
        return [
            {'key': 'missing-load', 'name': 'Missing load'},
            {'key': 'account-registration', 'name': 'Duplicate', 'load': lambda: ('Subject', 'Body')},
            {
                'key': 'unsafe-url',
                'name': 'Unsafe URL',
                'load': lambda: ('Subject', 'Body'),
                'url': 'javascript:alert(1)',
            },
            {
                'key': 'invalid-preview',
                'name': 'Invalid preview',
                'load': lambda: ('Subject', 'Body'),
                'preview': {1: 'not a string key'},
            },
            {'key': 'has/slash', 'name': 'Slash key', 'load': lambda: ('Subject', 'Body')},
        ]

    platform_mail_templates.connect(broken_receiver, dispatch_uid='test_broken_mail_template_receiver')
    platform_mail_templates.connect(invalid_templates, dispatch_uid='test_invalid_mail_templates')
    try:
        templates = get_platform_mail_templates()
        response = admin_client.get(reverse('eventyay_admin:admin.messages.templates'))
    finally:
        platform_mail_templates.disconnect(dispatch_uid='test_broken_mail_template_receiver')
        platform_mail_templates.disconnect(dispatch_uid='test_invalid_mail_templates')

    keys = [template['key'] for template in templates]
    assert 'missing-load' not in keys
    assert 'invalid-preview' not in keys
    assert 'has/slash' not in keys
    assert keys.count('account-registration') == 1
    unsafe_template = next(template for template in templates if template['key'] == 'unsafe-url')
    assert 'url' not in unsafe_template
    assert response.status_code == 200
    assert 'javascript:alert(1)' not in response.content.decode()


@pytest.mark.django_db
def test_disabled_plugin_templates_are_not_listed():
    receiver_called = False

    def disabled_plugin_templates(sender, **kwargs):
        nonlocal receiver_called
        receiver_called = True
        return {
            'key': 'disabled-plugin-template',
            'name': 'Disabled plugin template',
            'load': lambda: ('Subject', 'Body'),
        }

    platform_mail_templates.connect(
        disabled_plugin_templates,
        dispatch_uid='test_disabled_plugin_mail_templates',
    )
    plugin_app = SimpleNamespace(name='example.disabled_plugin')
    try:
        with (
            patch(
                'eventyay.control.views.admin_messages.apps.get_containing_app_config',
                return_value=plugin_app,
            ),
            patch.object(
                GlobalPluginConfig,
                'get_disabled_modules',
                return_value=frozenset({'example.disabled_plugin'}),
            ),
        ):
            keys = {template['key'] for template in get_platform_mail_templates()}
    finally:
        platform_mail_templates.disconnect(dispatch_uid='test_disabled_plugin_mail_templates')

    assert 'disabled-plugin-template' not in keys
    assert receiver_called is False


def _partial_plugin_templates(prefix, sender, **kwargs):
    return {'key': f'{prefix}-template', 'name': 'Partial template', 'load': lambda: ('Subject', 'Body')}


@pytest.mark.django_db
def test_disabled_plugin_partial_receivers_are_not_listed():
    receiver = functools.partial(_partial_plugin_templates, 'partial')
    platform_mail_templates.connect(receiver, weak=False, dispatch_uid='test_partial_plugin_mail_templates')
    plugin_app = SimpleNamespace(name='example.disabled_plugin')

    def containing_app(module):
        return plugin_app if module == __name__ else None

    try:
        with (
            patch(
                'eventyay.control.views.admin_messages.apps.get_containing_app_config',
                side_effect=containing_app,
            ),
            patch.object(
                GlobalPluginConfig,
                'get_disabled_modules',
                return_value=frozenset({'example.disabled_plugin'}),
            ),
        ):
            keys = {template['key'] for template in get_platform_mail_templates()}
    finally:
        platform_mail_templates.disconnect(dispatch_uid='test_partial_plugin_mail_templates')

    assert 'partial-template' not in keys


@pytest.mark.django_db
def test_every_template_detail_renders_preview(admin_client):
    for template in get_platform_mail_templates():
        url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': template['key']})
        response = admin_client.get(url)
        assert response.status_code == 200, template['key']
        assert 'data-tiptap-profile="email"' in response.content.decode().replace("'", '"')
        assert 'data-template-preview' in response.content.decode()


@pytest.mark.django_db
def test_talk_template_detail_uses_platform_default(admin_client):
    url = reverse(
        'eventyay_admin:admin.messages.template_detail',
        kwargs={'role': MailTemplateRoles.SUBMISSION_ACCEPT},
    )
    response = admin_client.get(url)
    assert response.context['versions'][0]['subject'] == 'Your proposal: {submission_title}'
    assert 'confirmation_link' in response.context['placeholder_keys']


@pytest.mark.django_db
def test_unknown_template_returns_404(admin_client):
    url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': 'does-not-exist'})
    assert admin_client.get(url).status_code == 404


@pytest.mark.django_db
def test_template_detail_requires_admin_session(client):
    user = User.objects.create_user(email='user@example.com', password='user-pass')
    client.force_login(user)
    url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': 'password-reset'})
    assert client.get(url).status_code in (302, 403)


@pytest.mark.django_db
def test_template_detail_shows_metadata_of_listed_row(admin_client):
    url = reverse(
        'eventyay_admin:admin.messages.template_detail',
        kwargs={'role': MailTemplateRoles.SUBMISSION_ACCEPT},
    )
    response = admin_client.get(url)
    assert str(response.context['role_label']) == 'Proposal acceptance'
    assert str(response.context['category']) == 'CfP'


@pytest.mark.django_db
def test_template_list_has_no_actions_column(admin_client):
    response = admin_client.get(reverse('eventyay_admin:admin.messages.templates'))
    assert 'Actions' not in response.content.decode()


@pytest.mark.django_db
def test_template_detail_offers_rendered_preview(admin_client):
    url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': 'account-registration'})
    content = admin_client.get(url).content.decode()
    assert 'data-mail-editor-mode="preview"' in content.replace("'", '"')
    assert reverse('eventyay_admin:admin.messages.preview') in content


@pytest.mark.django_db
def test_preview_endpoint_fills_placeholders_from_editor_html(admin_client):
    response = admin_client.post(
        reverse('eventyay_admin:admin.messages.preview'),
        data=json.dumps({'html': text_to_editor_html('Hello from {platform_name}!')}),
        content_type='application/json',
    )
    assert response.status_code == 200
    assert 'Hello from' in response.json()['html']
    assert 'Eventyay' in response.json()['html']


def _preview(admin_client, body, template_key=None):
    url = reverse('eventyay_admin:admin.messages.preview')
    if template_key:
        url += f'?template={template_key}'
    response = admin_client.post(
        url,
        data=json.dumps({'html': text_to_editor_html(body)}),
        content_type='application/json',
    )
    assert response.status_code == 200
    return response.json()['html']


@pytest.mark.django_db
def test_template_preview_replaces_every_placeholder_with_demo_data(admin_client):
    for template in get_platform_mail_templates():
        _, body = template['load']()
        html = _preview(admin_client, body, template['key'])
        assert not PLACEHOLDER_PATTERN.findall(html), template['key']


@pytest.mark.django_db
def test_template_preview_uses_template_specific_demo_data(admin_client):
    _, body = next(t for t in get_platform_mail_templates() if t['key'] == 'event-team-invitation')['load']()
    html = _preview(admin_client, body, 'event-team-invitation')
    assert 'Program committee' in html
    assert 'FOSSASIA' in html


@pytest.mark.django_db
def test_template_preview_highlights_demo_values(admin_client):
    html = _preview(admin_client, 'Welcome to {event_name}', 'password-reset')
    assert '<span class="placeholder"' in html
    assert '>FOSSASIA Summit 2026</span>' in html


@pytest.mark.django_db
def test_template_preview_keeps_links_working(admin_client):
    response = admin_client.post(
        reverse('eventyay_admin:admin.messages.preview') + '?template=password-reset',
        data=json.dumps({'html': '<p><a href="{event_url}">Open</a> {event_url}</p>'}),
        content_type='application/json',
    )
    html = response.json()['html']
    assert 'href="https://eventyay.com/fossasia/summit-2026/"' in html
    assert '>https://eventyay.com/fossasia/summit-2026/</span>' in html


@pytest.mark.django_db
def test_compose_preview_keeps_unknown_placeholders(admin_client):
    html = _preview(admin_client, 'Hello {user_name} from {event_name}')
    assert 'Jane Doe' in html
    assert '{event_name}' in html
    assert 'class="placeholder"' not in html


@pytest.mark.django_db
def test_template_detail_requests_demo_preview(admin_client):
    url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': 'password-reset'})
    content = admin_client.get(url).content.decode()
    assert reverse('eventyay_admin:admin.messages.preview') + '?template=password-reset' in content
