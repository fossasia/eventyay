import pytest
from django.core import mail

@pytest.mark.django_db
class TestContactOrganizer:
    """Test contact organizer functionality."""

    def test_contact_organizer_unauthenticated(self, client, organizer, event):
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = client.post(url, {
            'message': 'Hello, this is a test message.',
        })
        assert response.status_code == 401
        assert response.json()['success'] is False
        assert 'logged in' in response.json()['error']

    def test_contact_organizer_authenticated_missing_message(self, authenticated_client, organizer, event):
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': '',
        })
        assert response.status_code == 400
        assert response.json()['success'] is False

    def test_contact_organizer_authenticated_success(self, authenticated_client, organizer, event, user):
        # Configure event contact email so it doesn't return 400
        event.settings.contact_mail = 'contact@example.com'
        
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': 'This is a valid long enough message.',
        })
        assert response.status_code == 200
        assert response.json()['success'] is True

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ['contact@example.com']
        assert email.reply_to == [user.email]
        assert email.bcc == []

    def test_contact_organizer_authenticated_send_copy(self, authenticated_client, organizer, event, user):
        event.settings.contact_mail = 'contact@example.com'
        
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': 'This is a valid long enough message with send copy.',
            'send_copy': 'on',
        })
        assert response.status_code == 200
        assert response.json()['success'] is True

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ['contact@example.com']
        assert email.bcc == [user.email]

    def test_contact_organizer_placeholder_is_extracted(self):
        from django.template.loader import get_template
        from django.utils.translation.template import templatize

        source = get_template('common/includes/contact_organizer_modal.html').origin.name
        with open(source, encoding='utf-8') as f:
            extracted = templatize(f.read())
        assert "What's your question for the organizer?" in extracted

    def test_contact_organizer_modal_placeholder_translation(self, rf, user):
        from pathlib import Path
        import polib
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.utils.translation import override, trans_real

        request = rf.get('/test/contact/')
        request.user = user

        with override('en'):
            rendered = render_to_string(
                'common/includes/contact_organizer_modal.html',
                {'contact_url': '/test/contact/', 'request': request},
                request=request,
            )
            assert 'placeholder="What\'s your question for the organizer?"' in rendered

        po_path = Path(settings.BASE_DIR) / 'eventyay' / 'locale' / 'sv' / 'LC_MESSAGES' / 'django.po'
        mo_path = po_path.with_suffix('.mo')
        po_content = po_path.read_text(encoding='utf-8')
        assert 'msgid "What\'s your question for the organizer?"' in po_content
        assert 'msgstr "Vad vill du fråga arrangören?"' in po_content

        po = polib.pofile(str(po_path))
        po.save_as_mofile(str(mo_path))
        try:
            trans_real._translations.clear()
            with override('sv'):
                rendered_sv = render_to_string(
                    'common/includes/contact_organizer_modal.html',
                    {'contact_url': '/test/contact/', 'request': request},
                    request=request,
                )
                assert 'placeholder="Vad vill du fråga arrangören?"' in rendered_sv
        finally:
            if mo_path.exists():
                mo_path.unlink()
            trans_real._translations.clear()
