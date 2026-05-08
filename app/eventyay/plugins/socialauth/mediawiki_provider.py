from collections.abc import Mapping
from typing import Any

from allauth.account.models import EmailAddress
from allauth.socialaccount.providers.mediawiki.provider import MediaWikiProvider


class EventyayMediaWikiProvider(MediaWikiProvider):
    # Explicit package keeps allauth loading the upstream mediawiki urlconf
    # instead of deriving it from __module__, which would cause NoReverseMatch.
    package = "allauth.socialaccount.providers.mediawiki"

    def extract_extra_data(self, data: Mapping[str, Any]) -> dict[str, Any]:
        extra = super().extract_extra_data(data)
        if extra.get('email') is None and data.get('email'):
            extra['email'] = data['email']
        return extra

    def extract_email_addresses(self, data: Mapping[str, Any]) -> list[EmailAddress]:
        # When VERIFIED_EMAIL=True, trust the email even if confirmed_email=False.
        if self.get_settings().get('VERIFIED_EMAIL', False) and (email := data.get('email')):
            return [EmailAddress(email=email, verified=True, primary=True)]
        return super().extract_email_addresses(data)
