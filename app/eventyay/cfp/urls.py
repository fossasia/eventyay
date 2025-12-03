from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings

from .views import auth, event, locale, robots, user, wizard

app_name = "cfp"
urlpatterns = [
    path("", event.EventStartpage.as_view(), name="event.landing"),
    path("logout", auth.LogoutView.as_view(), name="event.logout"),
    path("auth/", auth.EventAuth.as_view(), name="event.auth"),
    path("reset", auth.ResetView.as_view(), name="event.reset"),
    path("login/", auth.LoginView.as_view(), name="event.login"),
    path(
        "reset/<token>",
        auth.RecoverView.as_view(),
        name="event.recover",
    ),
    path(
        "invite/<token>",
        auth.RecoverView.as_view(is_invite=True),
        name="event.new_recover",
    ),
    path("cfp", event.EventCfP.as_view(), name="event.start"),
    path("submit/", wizard.SubmitStartView.as_view(), name="event.submit"),
    path(
        "submit/<tmpid>/<step>/",
        wizard.SubmitWizard.as_view(),
        name="event.submit",
    ),
    path(
        "invitation/<code>/<invitation>",
        user.SubmissionInviteAcceptView.as_view(),
        name="invitation.view",
    ),
    path("me/", user.ProfileView.as_view(), name="event.user.view"),
    path(
        "me/submissions/",
        user.SubmissionsListView.as_view(),
        name="event.user.submissions",
    ),
    path(
        "me/mails/",
        user.MailListView.as_view(),
        name="event.user.mails",
    ),
    path(
        "me/submissions/<code>/",
        include(
            [
                path(
                    "",
                    user.SubmissionsEditView.as_view(),
                    name="event.user.submission.edit",
                ),
                path(
                    "withdraw",
                    user.SubmissionsWithdrawView.as_view(),
                    name="event.user.submission.withdraw",
                ),
                path(
                    "confirm",
                    user.SubmissionConfirmView.as_view(),
                    name="event.user.submission.confirm",
                ),
                path(
                    "discard",
                    user.SubmissionDraftDiscardView.as_view(),
                    name="event.user.submission.discard",
                ),
                path(
                    "invite",
                    user.SubmissionInviteView.as_view(),
                    name="event.user.submission.invite",
                ),
            ]
        ),
    ),
    path("locale/set", locale.LocaleSet.as_view(), name="locale.set"),
    path("robots.txt", robots.robots_txt, name="robots.txt"),
]

# Conditionally add account deletion route based on feature flag
# TODO: Current implementation doesn't fully remove user data (not GDPR compliant)
# Will be properly implemented in Account Settings
if getattr(settings, 'ENABLE_ACCOUNT_DELETION', False):
    urlpatterns.append(
        path(
            "me/delete",
            user.DeleteAccountView.as_view(),
            name="event.user.delete",
        )
    )
