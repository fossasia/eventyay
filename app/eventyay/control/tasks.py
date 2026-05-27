import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import ProtectedError
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User
from eventyay.base.models.log import LogEntry
from eventyay.celery_app import app
from eventyay.core.tasks import EventTask


logger = logging.getLogger(__name__)


@app.task(base=EventTask)
def clear_event_data(event):
    event.clear_data()


@app.task(name='eventyay.control.delete_organizer')
@scopes_disabled()
def delete_organizer_data(organizer_id: int, user_id: int | None = None) -> None:
    organizer = Organizer.objects.filter(pk=organizer_id).first()
    if organizer is None:
        logger.warning('Skipping organizer deletion because organizer %s no longer exists', organizer_id)
        return

    user = User.objects.filter(pk=user_id).first() if user_id is not None else None
    organizer_name = str(organizer.name)
    organizer_slug = organizer.slug
    event_ids = list(organizer.events.order_by('pk').values_list('pk', flat=True))

    try:
        for event_id in event_ids:
            try:
                event = Event.objects.select_related('organizer').get(pk=event_id)
            except Event.DoesNotExist:
                continue

            with transaction.atomic():
                event.delete_sub_objects()
                event.delete()

        if not Organizer.objects.filter(pk=organizer_id).exists():
            logger.info('Skipping final organizer cleanup because organizer %s was already deleted', organizer_id)
            return

        with transaction.atomic():
            organizer.delete_sub_objects()
            deleted_count, _ = organizer.delete()

        if deleted_count == 0:
            logger.info('Skipping organizer deletion log because organizer %s was already deleted', organizer_id)
            return

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Organizer),
            object_id=organizer_id,
            user=user,
            action_type='eventyay.organizer.deleted',
            data=json.dumps(
                {
                    'organizer_id': organizer_id,
                    'name': organizer_name,
                },
                sort_keys=True,
            ),
        )
    except ProtectedError as exc:
        protected_labels = ', '.join(sorted({obj._meta.label for obj in exc.protected_objects})) or 'unknown'
        organizer = Organizer.objects.filter(pk=organizer_id).first()
        if organizer is not None:
            organizer.log_action(
                'eventyay.organizer.deletion.failed',
                user=user,
                data={
                    'name': organizer_name,
                    'reason': protected_labels,
                },
            )
        logger.warning(
            'Async organizer deletion blocked for organizer %s by protected objects: %s',
            organizer_slug,
            protected_labels,
        )
        raise
