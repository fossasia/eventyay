import logging
from pathlib import Path

from django.core.files.storage import default_storage
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Submission, User
from eventyay.celery_app import app
from eventyay.common.image import process_image
from eventyay.common.signals import periodic_task

logger = logging.getLogger(__name__)


@app.task(name='pretalx.process_image')
def task_process_image(*, model: str, pk: int, field: str, generate_thumbnail: bool):
    models = {
        'Event': Event,
        'Submission': Submission,
        'User': User,
    }
    if model not in models:
        return

    with scopes_disabled():
        instance = models[model].objects.filter(pk=pk).first()
        if not instance:
            return

        image = getattr(instance, field, None)
        if not image:
            return

        try:
            process_image(image=image, generate_thumbnail=generate_thumbnail)
        except Exception as e:  # pragma: no cover
            logger.error('Could not process image %s: %s', image.path, e)


@app.task(name='pretalx.cleanup_file')
def task_cleanup_file(*, model: str, pk: int, field: str, path: str):
    models = {
        'Event': Event,
        'Submission': Submission,
        'User': User,
    }
    if model not in models:
        return

    with scopes_disabled():
        instance = models[model].objects.filter(pk=pk).first()
        if not instance:
            return

        file = getattr(instance, field, None)
        if file and file.path == path:
            # The save action that triggered this task did not go through and the file
            # is still in use, so we should not delete it.
            return

        real_path = Path(path)
        if real_path.exists():
            try:
                default_storage.delete(path)
            except OSError:  # pragma: no cover
                logger.error('Deleting file %s failed.', path)


@app.task(name='eventyay.common.tasks.send_periodic_signal')
def send_periodic_signal():
    """
    Celery task that sends the periodic_task signal.
    
    This task is intended to be run periodically by Celery beat (for example,
    via django-celery-beat's DatabaseScheduler) and triggers all signal receivers
    listening to the periodic_task signal, including process_scheduled_emails.
    
    Important:
    - django-celery-beat does NOT automatically create a schedule for this task.
    - You must ensure a corresponding PeriodicTask entry exists in the database
      (e.g. via a data migration, a management command, or by creating it
      manually through the Django admin) with the desired interval (such as
      every 60 seconds).
    """
    logger.info('Sending periodic_task signal')
    periodic_task.send(sender=None)
    logger.info('Periodic_task signal sent successfully')
