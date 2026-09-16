from django.utils.translation import gettext_lazy as _


GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
GMAIL_USERINFO_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
GMAIL_OAUTH_SCOPES = (GMAIL_SEND_SCOPE, GMAIL_USERINFO_EMAIL_SCOPE)
GMAIL_OAUTH_SCOPE = ' '.join(GMAIL_OAUTH_SCOPES)

GMAIL_OAUTH_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GMAIL_OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'

DEFAULT_GMAIL_DAILY_SEND_LIMIT = 450
DEFAULT_GMAIL_RATE_LIMIT_PER_MINUTE = 20

GMAIL_VENDOR_LABEL = _('Gmail / Google Workspace API')
