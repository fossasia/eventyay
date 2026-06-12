from css_inline import inline as inline_css
from django.conf import settings
from django.db import transaction
from django.template.loader import get_template
from django.utils.timezone import override
from django_scopes import scope, scopes_disabled

from eventyay.base.i18n import language
from eventyay.base.models import Event, LogEntry, NotificationSetting, OrganizerFollower, User
from eventyay.base.notifications import Notification, get_all_notification_types
from eventyay.base.services.mail import mail_send_task
from eventyay.base.services.tasks import ProfiledTask, TransactionAwareTask
from eventyay.celery_app import app
from eventyay.helpers.urls import build_absolute_uri
from eventyay.multidomain.urlreverse import build_absolute_uri as multidomain_build_absolute_uri


@app.task(base=TransactionAwareTask, acks_late=True, max_retries=9, default_retry_delay=900)
@scopes_disabled()
def notify(logentry_ids: list):
    if not isinstance(logentry_ids, list):
        logentry_ids = [logentry_ids]

    qs = LogEntry.all.select_related('event', 'event__organizer').filter(id__in=logentry_ids)

    _event, _at, notify_specific, notify_global = None, None, None, None
    for logentry in qs:
        if not logentry.event:
            break  # Ignore, we only have event-related notifications right now

        notification_type = logentry.notification_type

        if not notification_type:
            break  # No suitable plugin

        if _event != logentry.event or _at != logentry.action_type or notify_global is None:
            _event = logentry.event
            _at = logentry.action_type
            # All users that have the permission to get the notification
            users = logentry.event.get_users_with_permission(notification_type.required_permission).filter(
                notifications_send=True, is_active=True
            )
            if logentry.user:
                users = users.exclude(pk=logentry.user.pk)

            # Get all notification settings, both specific to this event as well as global
            notify_specific = {
                (ns.user, ns.method): ns.enabled
                for ns in NotificationSetting.objects.filter(
                    event=logentry.event,
                    action_type=notification_type.action_type,
                    user__pk__in=users.values_list('pk', flat=True),
                )
            }
            notify_global = {
                (ns.user, ns.method): ns.enabled
                for ns in NotificationSetting.objects.filter(
                    event__isnull=True,
                    action_type=notification_type.action_type,
                    user__pk__in=users.values_list('pk', flat=True),
                )
            }

        for um, enabled in notify_specific.items():
            user, method = um
            if enabled:
                send_notification.apply_async(args=(logentry.id, notification_type.action_type, user.pk, method))

        for um, enabled in notify_global.items():
            user, method = um
            if enabled and um not in notify_specific:
                send_notification.apply_async(args=(logentry.id, notification_type.action_type, user.pk, method))


@app.task(base=ProfiledTask, acks_late=True, max_retries=9, default_retry_delay=900)
def send_notification(logentry_id: int, action_type: str, user_id: int, method: str):
    logentry = LogEntry.all.get(id=logentry_id)
    if logentry.event:

        def sm():
            return scope(organizer=logentry.event.organizer)  # noqa
    else:

        def sm():
            return scopes_disabled()  # noqa

    with sm():
        user = User.objects.get(id=user_id)
        types = get_all_notification_types(logentry.event)
        notification_type = types.get(action_type)
        if not notification_type:
            return  # Ignore, e.g. plugin not active for this event

        with (
            language(user.locale),
            override(logentry.event.timezone if logentry.event else user.timezone),
        ):
            notification = notification_type.build_notification(logentry)

            if method == 'mail':
                send_notification_mail(notification, user)


def send_notification_mail(notification: Notification, user: User):
    ctx = {
        'site': settings.INSTANCE_NAME,
        'site_url': settings.SITE_URL,
        'color': settings.PRETIX_PRIMARY_COLOR,
        'notification': notification,
        'settings_url': build_absolute_uri(
            'eventyay_common:account.notifications',
        ),
        'disable_url': build_absolute_uri(
            'eventyay_common:account.notification.flip-off', kwargs={'token': user.notifications_token, 'id': user.pk}
        ),
    }

    tpl_html = get_template('pretixbase/email/notification.html')
    body_html = inline_css(tpl_html.render(ctx))
    tpl_plain = get_template('pretixbase/email/notification.txt')
    body_plain = tpl_plain.render(ctx)

    mail_send_task.apply_async(
        kwargs={
            'to': [user.email],
            'subject': '[{}] {}: {}'.format(
                settings.INSTANCE_NAME,
                notification.event.settings.mail_prefix or notification.event.slug.upper(),
                notification.title,
            ),
            'body': body_plain,
            'html': body_html,
            'sender': settings.MAIL_FROM,
            'headers': {},
            'user': user.pk,
        }
    )


@app.task(base=ProfiledTask, acks_late=True, max_retries=5, default_retry_delay=300)
@scopes_disabled()
def notify_organizer_followers(event_id: int):
    """
    Send an email notification to all followers of an organizer when a new event is published.

    This task is dispatched after an event transitions to ``live=True``.
    It respects the organizer's ``community_follow_enabled`` setting and each
    follower's locale / timezone.
    """
    with transaction.atomic():
        event = Event.objects.select_for_update().select_related('organizer').get(pk=event_id)

        if not event.live or not event.is_public or event.testmode:
            return

        organizer = event.organizer

        if LogEntry.objects.filter(event=event, action_type='eventyay.organizer.follower_notification.sent').exists():
            return

        event.log_action('eventyay.organizer.follower_notification.sent')

    try:
        organizer_url = multidomain_build_absolute_uri(
            organizer,
            'presale:organizer.index',
        )
        event_url = multidomain_build_absolute_uri(
            event,
            'presale:event.index',
        )
    except Exception:
        organizer_url = settings.SITE_URL
        event_url = settings.SITE_URL

    followers = (
        OrganizerFollower.objects.filter(organizer=organizer)
        .select_related('user')
        .iterator()
    )

    tpl_html = get_template('pretixbase/email/organizer_follower_new_event.html')
    tpl_plain = get_template('pretixbase/email/organizer_follower_new_event.txt')

    for follower in followers:
        user = follower.user
        if not user.is_active or not user.email:
            continue
        if not user.notifications_send:
            continue

        with language(user.locale or settings.LANGUAGE_CODE):
            ctx = {
                'site': settings.INSTANCE_NAME,
                'site_url': settings.SITE_URL,
                'organizer_name': organizer.name,
                'event_name': str(event.name),
                'event_url': event_url,
                'organizer_url': organizer_url,
            }
            body_plain = tpl_plain.render(ctx)
            body_html = inline_css(tpl_html.render(ctx))

            subject = '[{}] {}: {}'.format(
                settings.INSTANCE_NAME,
                organizer.name,
                str(event.name),
            )

            mail_send_task.apply_async(
                kwargs={
                    'to': [user.email],
                    'subject': subject,
                    'body': body_plain,
                    'html': body_html,
                    'sender': settings.MAIL_FROM,
                    'headers': {},
                    'user': user.pk,
                }
            )

