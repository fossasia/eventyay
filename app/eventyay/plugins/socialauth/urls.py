from django.urls import path

from . import views

urlpatterns = [
    path(
        'oauth_login/<str:provider>/',
        views.OAuthLoginView.as_view(),
        name='social.oauth.login',
    ),
    path(
        'control/global/social_auth/',
        views.SocialLoginView.as_view(),
        name='admin.global.social.auth.settings',
    ),
]
