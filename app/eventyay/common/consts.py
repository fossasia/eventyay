# Last time (in seconds) a user was forced to log in again
KEY_LAST_FORCE_LOGIN = 'eventyay_auth_login_time'
KEY_LAST_LOGIN_CHECK = 'eventyay_auth_last_used'

# Whether current session should bypass short timeout checks
KEY_LONG_SESSION = 'eventyay_auth_long_session'
KEY_PINNED_USER_AGENT = 'pinned_user_agent'

# Session key set by OAuthLoginView when the preferred-provider OAuth flow starts,
# so that post_login() knows to activate a long session.
KEY_SOCIAL_KEEP_LOGGED_IN = 'socialauth_keep_logged_in'
