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

    def populate_user(self, request, sociallogin, data):
        """
        Hook called after a user successfully authenticates, used to populate 
        User model fields from the social provider's data.
        
        This method is called BEFORE the user is saved, so it's the perfect place
        to extract and populate the wikimedia_username from OAuth extra_data.
        
        Fixes issue #1214: SSO Username Mapping
        """
        # Call parent to populate standard fields (email, username, etc.)
        user = super().populate_user(request, sociallogin, data)
        
        # Only process MediaWiki logins
        if sociallogin.account.provider != 'mediawiki':
            logger.debug(f'Skipping wikimedia_username extraction for provider: {sociallogin.account.provider}')
            return user

        # Extract extra_data from the social account
        extra_data = sociallogin.account.extra_data
        logger.info(f'Processing MediaWiki OAuth login. extra_data keys: {list(extra_data.keys())}')

        # Extract wikimedia username from extra_data
        # MediaWiki provides 'username' field, fallback to 'realname' if not present
        wikimedia_username = extra_data.get('username') or extra_data.get('realname') or ''
        
        if wikimedia_username:
            logger.info(f'Extracted wikimedia_username: {wikimedia_username}')
            user.wikimedia_username = wikimedia_username
        else:
            logger.warning(f'Could not extract wikimedia_username from extra_data: {extra_data}')
        
        return user

    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a social provider,
        but before the login is actually processed.
        
        Use this hook to update existing users' wikimedia_username if they log in
        again and their username has changed on MediaWiki.
        
        Fixes issue #1214: SSO Username Mapping
        """
        # Only process MediaWiki logins
        if sociallogin.account.provider != 'mediawiki':
            return

        # If this is a new user (no pk yet), populate_user will handle it
        if not sociallogin.user or not sociallogin.user.pk:
            logger.debug('New user, populate_user will set wikimedia_username')
            return

        # For existing users, update wikimedia_username if it has changed
        extra_data = sociallogin.account.extra_data
        wikimedia_username = extra_data.get('username') or extra_data.get('realname') or ''
        
        if wikimedia_username and sociallogin.user.wikimedia_username != wikimedia_username:
            logger.info(f'Updating wikimedia_username for existing user {sociallogin.user.email}: '
                       f'{sociallogin.user.wikimedia_username} -> {wikimedia_username}')
            sociallogin.user.wikimedia_username = wikimedia_username
            sociallogin.user.save(update_fields=['wikimedia_username'])
