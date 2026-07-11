from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from . import views

urlpatterns = [
    path('mails/compose/', views.ComposeMailChoice.as_view(), name='event.mail.compose'),
    path('mails/compose/teams/', views.ComposeTeamsMail.as_view(), name='event.mail.compose_teams'),
    path('mails/<int:pk>/', views.EditEmailQueueView.as_view(), name='event.mail.edit'),
    path('outbox/', views.OutboxListView.as_view(), name='event.mail.outbox'),
    path('outbox/send/<int:pk>/', views.SendEmailQueueView.as_view(), name='event.mail.outbox.send'),
    path('outbox/delete/<int:pk>/', views.DeleteEmailQueueView.as_view(), name='event.mail.outbox.delete'),
    path('outbox/purge/', views.PurgeEmailQueuesView.as_view(), name='event.mail.outbox.purge'),
    path('sendmail/', views.SenderView.as_view(), name='event.mail.send'),
    path('sendmail/sent/', views.SentMailView.as_view(), name='event.mail.sent'),
    path('sendmail/templates/', views.MailTemplatesView.as_view(), name='event.mail.templates'),
]
