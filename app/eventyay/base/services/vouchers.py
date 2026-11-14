from django.db import transaction
from django.db.models import Case, Q, TextField, Value, When
from django.db.models.functions import Concat
from django.utils.translation import gettext
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.base.email import get_email_context
from eventyay.base.i18n import language
from eventyay.base.models import Event, LogEntry, User, Voucher
from eventyay.base.services.mail import mail


def vouchers_send(
    event: Event,
    vouchers: list,
    subject: str,
    message: str,
    recipients: list,
    user: int,
    progress=None,
) -> None:
    with scope(organizer=event.organizer, event=event):
        vouchers = list(Voucher.objects.filter(event=event, id__in=vouchers).order_by('id'))
    user = User.objects.get(pk=user)
    for ir, r in enumerate(recipients):
        voucher_list = []
        for i in range(r['number']):
            voucher_list.append(vouchers.pop())
        with language(event.settings.locale):
            email_context = get_email_context(
                event=event,
                name=r.get('name') or '',
                voucher_list=[v.code for v in voucher_list],
            )
            mail(
                r['email'],
                subject,
                LazyI18nString(message),
                email_context,
                event,
                locale=event.settings.locale,
            )
            logs = []
            sent_msg = gettext('The voucher has been sent to {recipient}.').format(recipient=r['email'])
            for v in voucher_list:
                if r.get('tag') and r.get('tag') != v.tag:
                    v.tag = r.get('tag')
                logs.append(
                    v.log_action(
                        'eventyay.voucher.sent',
                        user=user,
                        data={
                            'recipient': r['email'],
                            'name': r.get('name'),
                            'subject': subject,
                            'message': message,
                        },
                        save=False,
                    )
                )

            update_kwargs = {
                'comment': Case(
                    When(Q(comment='') | Q(comment__isnull=True), then=Value(sent_msg)),
                    default=Concat('comment', Value(f'\n\n{sent_msg}'), output_field=TextField()),
                    output_field=TextField(),
                ),
            }
            if r.get('tag'):
                update_kwargs['tag'] = r['tag']

            with scope(organizer=event.organizer, event=event), transaction.atomic():
                if voucher_list:
                    Voucher.objects.filter(
                        event=event,
                        id__in=[v.id for v in voucher_list],
                    ).update(**update_kwargs)
                LogEntry.objects.bulk_create(logs, batch_size=500)

            if progress and ir % 50 == 0:
                progress(ir / len(recipients))
