from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from . import views

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/mails/compose/',
        views.ComposeMailChoice.as_view(),
        name='compose_email_choice'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/outbox/',
        views.OutboxListView.as_view(),
        name='outbox',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/outbox/send/<int:pk>/',
        views.SendEmailQueueView.as_view(),
        name='send_single'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/mails/<int:pk>/',
        views.EditEmailQueueView.as_view(),
        name='edit_mail'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/outbox/delete/<int:pk>/',
        views.DeleteEmailQueueView.as_view(),
        name='delete_single'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/outbox/purge/',
        views.PurgeEmailQueuesView.as_view(),
        name='purge_all'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/sendmail/',
        views.SenderView.as_view(),
        name='send',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/mails/compose/teams/',
        views.ComposeTeamsMail.as_view(),
        name='compose_email_teams'
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/sendmail/sent/',
        views.SentMailView.as_view(),
        name='sent',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/sendmail/templates/',
        views.MailTemplatesView.as_view(),
        name='templates',
    ),
]
