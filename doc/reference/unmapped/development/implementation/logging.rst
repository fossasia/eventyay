Logging and notifications
=========================

As eventyay is handling monetary transactions, we are very careful to make it possible to review all changes
in the system that lead to the current state.

.. _`logging`:

Logging changes
---------------

We log data changes to the database in a format that makes it possible to display those logs to a human, if
required. eventyay stores all those logs centrally in a model called :py:class:`eventyay.base.models.LogEntry`.
We recommend all relevant models to inherit from ``LoggedModel`` as it simplifies creating new log entries:

.. autoclass:: eventyay.base.models.LoggedModel
   :members: log_action, all_logentries

To actually log an action, you can just call the ``log_action`` method on your object:

.. code-block:: python

   order.log_action('eventyay.event.order.canceled', user=user, data={})

The positional ``action`` argument should represent the type of action and should be globally unique, we
recommend to prefix it with your package name, e.g. ``paypal.payment.rejected``. The ``user`` argument is
optional and may contain the user who performed the action. The optional ``data`` argument can contain
additional information about this action.

Logging form actions
""""""""""""""""""""

A very common use case is to log the changes to a model that have been done in a ``ModelForm``. In this case,
we generally use a custom ``form_valid`` method on our ``FormView`` that looks like this:

.. code-block:: python

    @transaction.atomic
    def form_valid(self, form):
        if form.has_changed():
            self.request.event.log_action('eventyay.event.changed', user=self.request.user, data={
                k: getattr(self.request.event, k) for k in form.changed_data
            })
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

It gets a little bit more complicated if your form allows file uploads:

.. code-block:: python

    @transaction.atomic
    def form_valid(self, form):
        if form.has_changed():
            self.request.event.log_action(
                'eventyay.event.changed', user=self.request.user, data={
                    k: (form.cleaned_data.get(k).name
                        if isinstance(form.cleaned_data.get(k), File)
                        else form.cleaned_data.get(k))
                    for k in form.changed_data
                }
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)


Displaying logs
"""""""""""""""

If you want to display the logs of a particular object to a user in the backend, you can use the
following ready-to-include template::

   {% include "eventyaycontrol/includes/logs.html" with obj=order %}

We now need a way to translate the action codes like ``eventyay.event.changed`` into human-readable
strings. The :py:attr:`eventyay.base.signals.logentry_display` signals allows you to do so. A simple
implementation could look like:

.. code-block:: python

    from django.utils.translation import gettext as _
    from eventyay.base.signals import logentry_display

    @receiver(signal=logentry_display)
    def eventyaycontrol_logentry_display(sender, logentry, **kwargs):
        plains = {
            'eventyay.event.order.paid': _('The order has been marked as paid.'),
            'eventyay.event.order.refunded': _('The order has been refunded.'),
            'eventyay.event.order.canceled': _('The order has been canceled.'),
            ...
        }
        if logentry.action_type in plains:
            return plains[logentry.action_type]

Sending notifications
---------------------

If you think that the logged information might be important or urgent enough to send out a notification to interested
organizers. In this case, you should listen for the :py:attr:`eventyay.base.signals.register_notification_types` signal
to register a notification type:

.. code-block:: python

    @receiver(register_notification_types)
    def register_my_notification_types(sender, **kwargs):
        return [MyNotificationType(sender)]

Note that this event is different than other events send out by eventyay: ``sender`` may be an event or ``None``. The
latter case is required to let the user define global notification preferences for all events.

You also need to implement a custom class that specifies how notifications should be handled for your notification type.
You should subclass the base ``NotificationType`` class and implement all its members:

.. autoclass:: eventyay.base.notifications.NotificationType
   :members: action_type, verbose_name, required_permission, build_notification

A simple implementation could look like this:

.. code-block:: python

    class MyNotificationType(NotificationType):
        required_permission = "can_view_orders"
        action_type = "eventyay.event.order.paid"
        verbose_name = _("Order has been paid")

        def build_notification(self, logentry: LogEntry):
            order = logentry.content_object

            order_url = build_absolute_uri(
                'control:event.order',
                kwargs={
                    'organizer': logentry.event.organizer.slug,
                    'event': logentry.event.slug,
                    'code': order.code
                }
            )

            n = Notification(
                event=logentry.event,
                title=_('Order {code} has been marked as paid').format(code=order.code),
                url=order_url
            )
            n.add_attribute(_('Order code'), order.code)
            n.add_action(_('View order details'), order_url)
            return n

As you can see, the relevant code is in the ``build_notification`` method that is supposed to create a ``Notification``
method that has a title, description, URL, attributes, and actions. The full definition of ``Notification`` is the
following:

.. autoclass:: eventyay.base.notifications.Notification
   :members: add_action, add_attribute


Logging technical information
-----------------------------

If you just want to log technical information to a log file on disk that does not need to be parsed
and displayed later, you can just use Python's ``logging`` module:

.. code-block:: python

   import logging

   logger = logging.getLogger(__name__)

   logger.info('Startup complete.')

This is also very useful to provide debugging information when an exception occurs:

.. code-block:: python

   try:
      foo()
   except:
      logger.exception('Error when calling foo()')  # Traceback will automatically be appended
      messages.error(request, _('An error occured.'))


Operational logs (privacy-safe)
-------------------------------

Most product areas already persist an audit trail as :class:`LogEntry`
via ``log_action`` (tickets ``LoggingMixin`` and talk/video/mail ``LogMixin``).
The process logger **mirrors** allowlisted ``log_action`` types. Unexpected
faults still use ``logger.exception`` / ``logger.error``. ``log_event`` only
attaches allowlisted extra fields (IDs, outcome, correlation); it is not a
second logging framework. Call sites do not need a helper in every file.

Each operational line includes:

- An ISO-8601 UTC ``datetime``
- ``component`` (``tickets``, ``talk``, ``video``, ``mail``, ``plugins``, ``core``)
- ``outcome=success`` or ``outcome=failure``
- ``action`` (the ``log_action`` type, or a choke-point name such as ``cart.error``)
- Opaque IDs only: ``event_id``, ``order_id``, ``order_code``, ``user_id``, ``object_id``, ``voucher_id``
- Correlation IDs: ``request_id`` (HTTP ``X-Request-ID`` or generated) and ``job_id`` (Celery task id)

Do **not** log emails, names, phones, addresses, payment instrument data,
tokens, cookies, API keys, webhook secrets, voucher secrets, or raw
request/response bodies. ``log_action`` ``data`` payloads are never copied
to the process log. Only allowlisted keys such as ``provider`` (payment
provider identifier) and numeric IDs are promoted onto the log line.

Every HTTP route is covered by ``CorrelationIdMiddleware`` (first in
``MIDDLEWARE``): correlation IDs on all requests, ``core.request.start``
on entry, ``core.request.end`` on completion (route name, status, duration;
no query strings), and ``core.auth.denied`` / ``core.permission.denied`` /
``core.request.error`` for 401, 403, and 5xx. Static/media and health
paths are skipped here; health dependency failures use ``health.check``.
Live WebSocket connect/abnormal close
and ``ConsumerException`` cover video commands; mutating APIs go through
``log_action`` prefixes, video ``AuditLog.save``, or choke-point ``log_event``
calls. Video ``AuditLog`` rows are mirrored without copying ``data`` (chat
message edits and profile dumps stay out of the process log).

Levels: ``INFO`` for successful lifecycle transitions, ``WARNING`` for
expected business failures, ``ERROR`` (via ``logger.exception``) only for
unexpected faults.

Skipped to keep volume low: scanner heartbeat ``eventyay.device.updated``,
generic ``eventyay.event.settings`` saves, organizer/order comments (not
submission review comments), static/media/health-success probes,
and per-user chat join/leave. Occupancy is logged at aggregate room-count
changes only. Page views still emit ``request.end`` with route/status/duration
and no query string. Attendee profile dumps are not mirrored.

Areas:

- **tickets**: attendee cart/checkout/order/payment/refund, products,
  quotas, vouchers, waiting list, check-in, devices/gates, payment-provider
  config, ticket/badge PDF layouts, lock timeouts/release, geocoding request
  failures (no address text), EU VIES VAT lookup unavailability (no VAT ID),
  ticket PDF generate failures (order code only), API quota-exceeded, and
  data-shred failures.
- **talk**: speaker/attendee CfP and submissions, reviews, schedule
  publish, tracks, access codes, organizer event/talk-data updates,
  public schedule and schedule-editor HTTP failures (status only, no
  JSON/PII), invalid API tokens, Etherpad pad create and misconfiguration,
  talk-schedule widget fetch failures (no URL), and speaker-import avatar
  download failures (no URL).
- **video**: room create/update/delete (REST and ``AuditLog`` ``event.room.*``),
  aggregate room occupancy (count only, no user ids), stream-schedule
  create/update/delete, BBB recording start/stop when a recorded call is
  created or ended, recording listing (``recording.fetch``, no XML/URLs),
  LoungeMesh token exchange/refresh as ``media.callback`` (type only),
  feature-flag writes and disabled-provider evaluation (flag name only),
  live WebSocket connect/abnormal close, BBB/Janus/Jitsi/Zoom/LoungeMesh
  connection errors, WHEP/HLS/captions, live JWT/kiosk auth failures,
  and browser-reported failures via ``event.client_log``. There is no
  BBB/Janus/Zoom inbound recording webhook in this repository.
- **mail**: enqueue (``QueuedMail`` / ``EmailQueue``, ids and recipient
  counts only), outbox worker dispatch, send success/failure, template
  render failures, SMTP 554/571 as ``mail.complaint``, other recipient 5xx
  and Gmail permanent rejection as ``mail.bounce`` (smtp code, no addresses),
  order-email actions, Gmail OAuth connect/callback/revoke (no tokens), CID
  image fetch 5xx, and test-send failures. There is no SES/SNS complaint
  inbound webhook in this repository.
- **plugins**: plugin enable/disable, outbound webhook status/duration
  (no URL/body), inbound Stripe signature validation, billing Stripe API
  errors (no card or customer payloads), meetup RSVP Stripe confirm/refund
  (order code only), bank-import parse and lock-timeout retries.
- **core**: ``request.start`` and ``request.end`` (route when resolved, status,
  duration), 401/403/5xx, control and common login without credentials,
  Celery ``job.enqueue`` / ``job.start`` / ``job.finish`` / ``job.retry`` / ``job.fail``
  (task name and id, not args), config load (no setting values),
  DB/cache/redis/queue health failures (one structured ``logger.exception``
  line with extras), social-login provider errors,
  failed 2FA, Turnstile misconfig/network, telemetry HTTP failures.

Production format (console handler ``verbose``). The logger message is the
action name; outcome lives in extras::

    LEVEL <iso-8601-utc> eventyay.<component>: <action> datetime=... component=... outcome=... action=... [error_code=...] [event_id=...] [order_code=...] [request_id=...] [job_id=...]

Examples (PII-free)::

    INFO 2026-09-20T15:45:01Z eventyay.tickets: eventyay.event.order.placed datetime=2026-09-20T15:45:01Z component=tickets outcome=success action=eventyay.event.order.placed event_id=12 order_id=34 order_code=ABC12 model=Order request_id=req-7f3a9c

    INFO 2026-09-20T15:45:08Z eventyay.tickets: eventyay.event.order.paid datetime=2026-09-20T15:45:08Z component=tickets outcome=success action=eventyay.event.order.paid event_id=12 order_id=34 order_code=ABC12 model=Order request_id=req-7f3a9c

    INFO 2026-09-20T15:45:04Z eventyay.tickets: eventyay.event.order.payment.started datetime=2026-09-20T15:45:04Z component=tickets outcome=success action=eventyay.event.order.payment.started event_id=12 order_code=ABC12 payment_provider=stripe payment_id=88 payment_local_id=2 request_id=req-7f3a9c

    INFO 2026-09-20T15:45:05Z eventyay.tickets: payment.handoff datetime=2026-09-20T15:45:05Z component=tickets outcome=success action=payment.handoff event_id=12 payment_provider=stripe request_id=req-7f3a9c

    WARNING 2026-09-20T15:45:06Z eventyay.tickets: eventyay.event.order.payment.failed datetime=2026-09-20T15:45:06Z component=tickets outcome=failure action=eventyay.event.order.payment.failed event_id=12 order_code=ABC12 payment_provider=stripe request_id=req-7f3a9c

    INFO 2026-09-20T15:46:01Z eventyay.tickets: eventyay.event.order.canceled datetime=2026-09-20T15:46:01Z component=tickets outcome=success action=eventyay.event.order.canceled event_id=12 order_code=ABC12 user_id=9 is_orga_action=True request_id=req-7f3a9c

    INFO 2026-09-20T15:46:10Z eventyay.tickets: eventyay.event.order.refunded datetime=2026-09-20T15:46:10Z component=tickets outcome=success action=eventyay.event.order.refunded event_id=12 order_code=ABC12 request_id=req-7f3a9c

    INFO 2026-09-20T16:00:00Z eventyay.tickets: eventyay.event.checkin datetime=2026-09-20T16:00:00Z component=tickets outcome=success action=eventyay.event.checkin event_id=12 checkin_list_id=5 position_id=77 request_id=req-7f3a9c

    WARNING 2026-09-20T16:00:02Z eventyay.tickets: checkin.error datetime=2026-09-20T16:00:02Z component=tickets outcome=failure action=checkin.error error_code=already_redeemed event_id=12 request_id=req-7f3a9c

    INFO 2026-09-20T15:44:50Z eventyay.tickets: voucher.apply datetime=2026-09-20T15:44:50Z component=tickets outcome=success action=voucher.apply event_id=12 job_id=c0ffee12-task

    WARNING 2026-09-20T15:44:40Z eventyay.tickets: cart.error datetime=2026-09-20T15:44:40Z component=tickets outcome=failure action=cart.error error_code=cart_error event_id=12 request_id=req-7f3a9c

    WARNING 2026-09-20T15:44:41Z eventyay.tickets: checkout.cart_invalid datetime=2026-09-20T15:44:41Z component=tickets outcome=failure action=checkout.cart_invalid error_code=cart_invalid event_id=12 request_id=req-7f3a9c

    INFO 2026-09-20T16:10:00Z eventyay.talk: eventyay.submission.create datetime=2026-09-20T16:10:00Z component=talk outcome=success action=eventyay.submission.create event_id=12 object_id=99 request_id=req-7f3a9c

    INFO 2026-09-20T16:11:00Z eventyay.talk: eventyay.schedule.release datetime=2026-09-20T16:11:00Z component=talk outcome=success action=eventyay.schedule.release event_id=12 request_id=req-7f3a9c

    WARNING 2026-09-20T16:12:00Z eventyay.video: janus.connection datetime=2026-09-20T16:12:00Z component=video outcome=failure action=janus.connection error_code=janus_error request_id=req-7f3a9c

    INFO 2026-09-20T16:12:05Z eventyay.video: connection.get datetime=2026-09-20T16:12:05Z component=video outcome=success action=connection.get backend=bbb status=200 duration_ms=88 event_id=12

    WARNING 2026-09-20T16:12:08Z eventyay.video: iframe.error datetime=2026-09-20T16:12:08Z component=video outcome=failure action=iframe.error error_code=iframe_error backend=bbb event_id=12 user_id=9

    INFO 2026-09-20T16:13:00Z eventyay.mail: mail.send datetime=2026-09-20T16:13:00Z component=mail outcome=success action=mail.send event_id=12 order_id=34 mail_type=order job_id=c0ffee12-task

    WARNING 2026-09-20T16:13:02Z eventyay.mail: eventyay.event.order.email.error datetime=2026-09-20T16:13:02Z component=mail outcome=failure action=eventyay.event.order.email.error event_id=12 order_code=ABC12 job_id=c0ffee12-task

    INFO 2026-09-20T16:14:00Z eventyay.plugins: webhook.outbound datetime=2026-09-20T16:14:00Z component=plugins outcome=success action=webhook.outbound webhook_id=8 status=200 duration_ms=41 retry_count=0 job_id=c0ffee12-task

    WARNING 2026-09-20T16:15:00Z eventyay.core: permission.denied datetime=2026-09-20T16:15:00Z component=core outcome=failure action=permission.denied error_code=forbidden status=403 user_id=9 request_id=req-7f3a9c

    INFO 2026-09-20T16:16:00Z eventyay.core: eventyay.team.created datetime=2026-09-20T16:16:00Z component=core outcome=success action=eventyay.team.created object_id=3 is_orga_action=True request_id=req-7f3a9c

    INFO 2026-09-20T16:16:10Z eventyay.talk: eventyay.event.update datetime=2026-09-20T16:16:10Z component=talk outcome=success action=eventyay.event.update event_id=12 is_orga_action=True request_id=req-7f3a9c

    WARNING 2026-09-20T16:17:00Z eventyay.talk: schedule.save datetime=2026-09-20T16:17:00Z component=talk outcome=failure action=schedule.save error_code=http_error backend=schedule_editor status=500

    INFO 2026-09-20T16:18:00Z eventyay.video: auth.user.banned datetime=2026-09-20T16:18:00Z component=video outcome=success action=auth.user.banned event_id=12 user_id=9 object_id=u1 model=AuditLog request_id=req-7f3a9c

    WARNING 2026-09-20T16:18:10Z eventyay.tickets: lock.timeout datetime=2026-09-20T16:18:10Z component=tickets outcome=failure action=lock.timeout error_code=lock_timeout request_id=req-7f3a9c

    WARNING 2026-09-20T16:18:20Z eventyay.video: upload datetime=2026-09-20T16:18:20Z component=video outcome=failure action=upload error_code=file.type event_id=12 request_id=req-7f3a9c
