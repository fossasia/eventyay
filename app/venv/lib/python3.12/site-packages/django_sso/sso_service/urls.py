from django.urls import path

from . import views

urlpatterns = [

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout, name='logout'),

    path('sso/test/', views.for_logged_only_view),
    path('sso/accept/', views.authorize_from_sso_view),
    path('sso/event/', views.event_acceptor_view),
]
