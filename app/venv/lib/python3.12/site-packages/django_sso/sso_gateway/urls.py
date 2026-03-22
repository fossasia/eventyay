from django.urls import path
from django.views.generic import TemplateView
from django.conf import settings

from . import views


urlpatterns = [
	path('login/', views.LoginView.as_view(), name="login"),
	path('logout/', views.LogoutView.as_view(), name="logout"),

	path('sso/obtain/', views.ObtainView.as_view(), name="obtain"),
	path('sso/get/', views.GetAuthenticationRequestView.as_view(), name="get"),
	path('sso/make_used/', views.MakeUsedView.as_view(), name="make_used"),
	path('sso/deauthenticate/', views.DeauthenticateView.as_view(), name="deauthenticate_view"),
	path('__welcome/', TemplateView.as_view(template_name='django_sso/welcome.html'), name="welcome"),
]

if settings.DEBUG:
	urlpatterns.append(
		path('sso/debug/update_event/', views.DebugUpdateEvent.as_view(), name="debug_update_event"),
	)
