import pytest
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.mail import MailTemplateRoles
from eventyay.control.views.admin_messages import (
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


def test_every_template_has_content():
    for template in get_platform_mail_templates():
        subject, body = template['load']()
        assert subject.strip(), template['key']
        assert body.strip(), template['key']


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


def test_text_to_editor_html_keeps_paragraphs_and_placeholders():
    html = text_to_editor_html('Hello {name},\nsee <this>\n\nBye {event}')
    assert html == (
        '<p>Hello <span data-variable="name"></span>,<br>see &lt;this&gt;</p>'
        '<p>Bye <span data-variable="event"></span></p>'
    )


@pytest.mark.django_db
def test_template_list_links_every_template(admin_client):
    response = admin_client.get(reverse('eventyay_admin:admin.messages.templates'))
    assert response.status_code == 200
    content = response.content.decode()
    for template in get_platform_mail_templates():
        url = reverse('eventyay_admin:admin.messages.template_detail', kwargs={'role': template['key']})
        assert url in content


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
