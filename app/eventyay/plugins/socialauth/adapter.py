import functools
import logging
from typing import cast

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    # Override to setup User-Agent to follow Wikimedia policy
    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    def get_requests_session(self):
        # The self.request was populated by BaseAdapter.
        dj_request = cast(HttpRequest, self.request)
        site_url = dj_request.build_absolute_uri('/')
        try:
            contact = settings.ADMINS[0][1]
        except (AttributeError, IndexError):
            contact = 'webmaster@eventyay.com'
        user_agent = f'eventyay/1.0 ({site_url}; {contact})'

        import requests

        session = requests.Session()
        session.headers.update({'User-Agent': user_agent})
        session.request = functools.partial(session.request, timeout=app_settings.REQUESTS_TIMEOUT)
        return session

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error('Error while authorizing with %s: %s - %s', provider, error, exception)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse('control:index')))

    def pre_social_login(self, request, sociallogin):
        """
        Invoked after a user successfully authenticates via a social provider,
        but before the login is fully processed.
        
        This is the ideal place to extract and populate the wikimedia_username
        from the OAuth provider's extra_data.
        
        Fixes issue #1214: SSO Username Mapping
        """
        # Only process MediaWiki logins
        if sociallogin.account.provider != 'mediawiki':
            logger.debug(f'Skipping pre_social_login for provider: {sociallogin.account.provider}')
            return

        # Extract extra_data from the social account
        extra_data = sociallogin.account.extra_data
        logger.info(f'Processing MediaWiki OAuth login. extra_data keys: {list(extra_data.keys())}')

        # Extract wikimedia username from extra_data
        # MediaWiki provides 'username' field, fallback to 'realname' if not present
        wikimedia_username = extra_data.get('username') or extra_data.get('realname') or ''
        
        if wikimedia_username:
            logger.info(f'Extracted wikimedia_username: {wikimedia_username}')
            
            # Populate the user's wikimedia_username field
            user = sociallogin.user
            user.wikimedia_username = wikimedia_username
            
            # Save if user already exists (update case)
            if user.pk:
                user.save(update_fields=['wikimedia_username'])
                logger.info(f'Updated existing user {user.email} with wikimedia_username: {wikimedia_username}')
            else:
                logger.info(f'Will create new user with wikimedia_username: {wikimedia_username}')
        else:
            logger.warning(f'Could not extract wikimedia_username from extra_data: {extra_data}')
