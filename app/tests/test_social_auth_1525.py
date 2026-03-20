from unittest.mock import MagicMock
import pytest
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from allauth.socialaccount.models import SocialApp
from eventyay.base.settings import GlobalSettingsObject
from eventyay.plugins.socialauth.adapter import CustomSocialAccountAdapter
from eventyay.plugins.socialauth.views import OAuthLoginView, OAuthReturnView, SocialLoginView

@pytest.mark.django_db
class TestSocialAuthBypassBlocked:
    """Tests for the allauth URL bypass prevention (pre_social_login hook)."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.gs = GlobalSettingsObject()
        self.factory = RequestFactory()
        self.adapter = CustomSocialAccountAdapter()
        self.gs.settings.set('login_providers', {
            'google': {'state': False, 'client_id': 'goog_id', 'secret': 'goog_secret'},
            'github': {'state': True, 'client_id': 'gh_id', 'secret': 'gh_secret'},
            'mediawiki': {'state': False, 'client_id': 'mw_id', 'secret': 'mw_secret'},
            'preferred_provider': '',
        })

    def _make_request(self):
        request = self.factory.get('/accounts/google/login/')
        request.session = SessionStore()
        # Django messages framework requires message storage
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def _make_sociallogin(self, provider):
        sociallogin = MagicMock()
        sociallogin.account.provider = provider
        return sociallogin

    def test_disabled_provider_raises_immediate_response(self):
        """
        Hitting a disabled provider's allauth URL must raise ImmediateHttpResponse
        and redirect back to the login page.
        """
        request = self._make_request()
        sociallogin = self._make_sociallogin('google')

        with pytest.raises(ImmediateHttpResponse) as exc:
            self.adapter.pre_social_login(request, sociallogin)

        assert exc.value.response["Location"] == reverse("eventyay_common:auth.login")

    def test_disabled_provider_sets_error_message(self):
        """
        The error message must be 'This social login provider is currently disabled.'
        """
        request = self._make_request()
        sociallogin = self._make_sociallogin('google')

        with pytest.raises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

        messages_list = list(get_messages(request))
        assert len(messages_list) == 1
        assert 'This social login provider is currently disabled.' in str(messages_list[0])

    def test_enabled_provider_passes_through(self):
        """An enabled provider must NOT raise any exception."""
        request = self._make_request()
        sociallogin = self._make_sociallogin('github')

        # Should not raise — just returns None
        result = self.adapter.pre_social_login(request, sociallogin)
        assert result is None

    def test_unknown_provider_is_blocked_and_redirects(self):
        """
        A provider not in the settings dict at all must be blocked and redirected.
        """
        request = self._make_request()
        sociallogin = self._make_sociallogin('facebook')

        with pytest.raises(ImmediateHttpResponse) as exc:
            self.adapter.pre_social_login(request, sociallogin)

        assert exc.value.response["Location"] == reverse("eventyay_common:auth.login")

    def test_empty_settings_blocks_all_and_redirects(self):
        """If login_providers is empty/None, ALL providers must be blocked and redirected."""
        self.gs.settings.set('login_providers', {})
        request = self._make_request()
        sociallogin = self._make_sociallogin('github')

        with pytest.raises(ImmediateHttpResponse) as exc:
            self.adapter.pre_social_login(request, sociallogin)

        assert exc.value.response["Location"] == reverse("eventyay_common:auth.login")


@pytest.mark.django_db
class TestPreferredProviderAdminLogic:
    """Tests for the admin view validation of preferred_provider."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.gs = GlobalSettingsObject()
        self.gs.settings.set('login_providers', {
            'google': {'state': True, 'client_id': 'goog_id', 'secret': 'goog_secret'},
            'github': {'state': True, 'client_id': 'gh_id', 'secret': 'gh_secret'},
            'mediawiki': {'state': False, 'client_id': 'mw_id', 'secret': 'mw_secret'},
            'preferred_provider': 'google',
        })

    def test_disabling_preferred_provider_clears_preference(self):
        """
        If the preferred provider gets disabled, the preference must auto-clear.
        """
        view = SocialLoginView()
        login_providers = self.gs.settings.get('login_providers', as_type=dict)

        # Simulate disabling Google (which is currently preferred)
        factory = RequestFactory()
        request = factory.post('/', data={'google_login': 'disabled'})
        view.update_provider_state(request, 'google', login_providers)

        # Google should be disabled and no longer preferred
        assert login_providers['google']['state'] is False
        assert login_providers['preferred_provider'] == ''

    def test_clearing_credentials_deletes_social_app(self):
        """
        If credentials are cleared in the admin UI, the SocialApp must be deleted.
        """
        
        # Pre-create a SocialApp
        SocialApp.objects.get_or_create(
            provider='github',
            defaults={'client_id': 'old_id', 'secret': 'old_secret', 'name': 'GitHub'}
        )
        
        view = SocialLoginView()
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        
        # Simulate clearing credentials (empty strings in POST)
        factory = RequestFactory()
        request = factory.post('/', data={
            'save_credentials': 'credentials',
            'github_client_id': '',
            'github_secret': '',
        })
        
        view.update_credentials(request, 'github', login_providers)
        
        # Dict should be updated
        assert login_providers['github']['client_id'] == ''
        assert login_providers['github']['secret'] == ''
        
        # SocialApp should be deleted
        assert not SocialApp.objects.filter(provider='github').exists()


@pytest.mark.django_db
class TestPreferredProviderSessionLogic:
    """Tests for session-based 'keep me logged in' via preferred provider."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.gs = GlobalSettingsObject()
        self.gs.settings.set('login_providers', {
            'google': {'state': True, 'client_id': 'goog_id', 'secret': 'goog_secret'},
            'github': {'state': True, 'client_id': 'gh_id', 'secret': 'gh_secret'},
            'mediawiki': {'state': False, 'client_id': 'mw_id', 'secret': 'mw_secret'},
            'preferred_provider': 'github',
        })

    def test_oauth_login_view_sets_session_for_provider(self, monkeypatch):
        """
        Integration test: OAuthLoginView must store the provider in session.
        """
        factory = RequestFactory()
        request = factory.get('/auth/login/github/')
        request.session = SessionStore()

        view = OAuthLoginView.as_view()
        # Mocking dependency to avoid full provider initialization
        from eventyay.plugins.socialauth import views
        
        mock_adapter = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_login_url.return_value = 'http://example.com/login'
        mock_adapter.get_provider.return_value = mock_provider
        
        monkeypatch.setattr(views, 'adapter', mock_adapter)
        
        # Call the view directly, expecting a redirect HttpResponse
        view(request, provider='github')

        assert request.session.get('socialauth_provider') == 'github'

    def test_oauth_return_view_uses_keep_logged_in_for_preferred_provider(self, monkeypatch):
        """
        Integration test: Verify keep_logged_in=True for the preferred provider.
        """
        factory = RequestFactory()
        session = SessionStore()
        session['socialauth_provider'] = 'github'
        request = factory.get('/auth/return/github/')
        request.session = session

        called = {}

        def fake_process_login_and_set_cookie(request, user, keep_logged_in):
            called['keep_logged_in'] = keep_logged_in
            return MagicMock()

        monkeypatch.setattr(
            'eventyay.plugins.socialauth.views.process_login_and_set_cookie',
            fake_process_login_and_set_cookie,
        )
        monkeypatch.setattr(
            'eventyay.plugins.socialauth.views.OAuthReturnView.get_or_create_user',
            lambda self, req: MagicMock(),
        )

        view = OAuthReturnView.as_view()
        view(request)

        assert called.get('keep_logged_in') is True

    def test_oauth_return_view_no_keep_logged_in_for_non_preferred_provider(self, monkeypatch):
        """
        Integration test: Verify keep_logged_in=False for non-preferred providers.
        """
        factory = RequestFactory()
        session = SessionStore()
        session['socialauth_provider'] = 'google'
        request = factory.get('/auth/return/google/')
        request.session = session

        called = {}

        def fake_process_login_and_set_cookie(request, user, keep_logged_in):
            called['keep_logged_in'] = keep_logged_in
            return MagicMock()

        monkeypatch.setattr(
            'eventyay.plugins.socialauth.views.process_login_and_set_cookie',
            fake_process_login_and_set_cookie,
        )
        monkeypatch.setattr(
            'eventyay.plugins.socialauth.views.OAuthReturnView.get_or_create_user',
            lambda self, req: MagicMock(),
        )

        view = OAuthReturnView.as_view()
        view(request)

        assert called.get('keep_logged_in') is False
