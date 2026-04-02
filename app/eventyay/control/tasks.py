import logging

from django.db import transaction
from django.db.models import ProtectedError
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User
from eventyay.celery_app import app
from eventyay.core.tasks import EventTask


logger = logging.getLogger(__name__)


@app.task(base=EventTask)
def clear_event_data(event):
    event.clear_data()


@app.task(name='eventyay.control.delete_organizer')
@scopes_disabled()
def delete_organizer_data(organizer_id: int, user_id: int | None = None) -> None:
    try:
        organizer = Organizer.objects.get(pk=organizer_id)
    except Organizer.DoesNotExist:
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

        with transaction.atomic():
            organizer = Organizer.objects.get(pk=organizer_id)
            organizer.delete_sub_objects()
            organizer.delete()

        if user is not None:
            user.log_action(
                'pretix.organizer.deleted',
                user=user,
                data={
                    'organizer_id': organizer_id,
                    'name': organizer_name,
                },
            )
    except ProtectedError as exc:
        protected_labels = ', '.join(sorted({obj._meta.label for obj in exc.protected_objects})) or 'unknown'
        logger.warning(
            'Async organizer deletion blocked for organizer %s by protected objects: %s',
            organizer_slug,
            protected_labels,
        )
        raise
