import logging
import os

from celery import Celery
from celery.signals import after_task_publish, task_failure, task_postrun, task_prerun

os.environ.setdefault('EVY_RUNNING_ENVIRONMENT', 'development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')

from django.conf import settings

from eventyay.base.operational_logging import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    bind_job_id,
    log_event,
    reset_job_id,
)

logger = logging.getLogger(__name__)

app = Celery('eventyay')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@after_task_publish.connect(weak=False)
def log_operational_job_enqueue(sender=None, headers=None, **kwargs):
    task_id = (headers or {}).get('id')
    log_event('core', 'job.enqueue', OUTCOME_SUCCESS, job_name=sender, job_id=task_id)


@task_prerun.connect(weak=False)
def bind_operational_job_id(sender=None, task_id=None, **kwargs):
    if task_id:
        bind_job_id(task_id)
    log_event('core', 'job.start', OUTCOME_SUCCESS, job_name=getattr(sender, 'name', None), job_id=task_id)


@task_postrun.connect(weak=False)
def reset_operational_job_id(sender=None, task_id=None, state=None, **kwargs):
    job_name = getattr(sender, 'name', None)
    if state == 'SUCCESS':
        log_event('core', 'job.finish', OUTCOME_SUCCESS, job_name=job_name, job_id=task_id, job_state=state)
    elif state == 'RETRY':
        log_event('core', 'job.retry', OUTCOME_FAILURE, error_code='retry', job_name=job_name, job_id=task_id)
    reset_job_id()


@task_failure.connect(weak=False)
def log_operational_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    job_name = getattr(sender, 'name', None)
    error_code = type(exception).__name__ if exception is not None else 'task_failure'
    if not error_code.replace('_', '').isalnum():
        error_code = 'task_failure'
    log_event('core', 'job.fail', OUTCOME_FAILURE, error_code=error_code, job_name=job_name, job_id=task_id)
