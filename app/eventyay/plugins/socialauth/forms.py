from allauth.account.utils import filter_users_by_email, perform_login
from allauth.socialaccount import app_settings
from allauth.socialaccount.forms import SignupForm

from .email import ensure_verified_email_for_user


class MediaWikiSocialSignupForm(SignupForm):
    def try_save(self, request):
        if self.account_already_exists and self.sociallogin and self.sociallogin.provider.id == 'mediawiki':
            email = self.cleaned_data.get('email')
            if email and app_settings.EMAIL_AUTHENTICATION:
                users = filter_users_by_email(email, prefer_verified=True)
                if users:
                    user = users[0]
                    self.sociallogin.user = user
                    self.sociallogin._did_authenticate_by_email = email
                    ensure_verified_email_for_user(user, email)
                    self.sociallogin._accept_login(request)
                    return user, perform_login(
                        request,
                        user,
                        email_verification=app_settings.EMAIL_VERIFICATION,
                        redirect_url=self.sociallogin.get_redirect_url(request),
                        signal_kwargs={'sociallogin': self.sociallogin},
                    )
        return super().try_save(request)
