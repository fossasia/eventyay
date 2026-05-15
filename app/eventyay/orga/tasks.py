import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import jwt
import requests
from django.conf import settings

from eventyay.celery_app import app

logger = logging.getLogger(__name__)


def generate_sso_token(user_email):
    jwt_payload = {
        'email': user_email,
        'has_perms': 'base.edit_schedule',
        'exp': datetime.now(timezone.utc) + timedelta(hours=1),
        'iat': datetime.now(timezone.utc),
    }
    jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm='HS256')
    return jwt_token


def set_header_token(user_email):
    token = generate_sso_token(user_email)
    # Define the headers, including the Authorization header with the Bearer token
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    return headers


@app.task(
    bind=True,
    name='eventyay.orga.trigger_public_schedule',
    max_retries=3,
    default_retry_delay=60,
)
def trigger_public_schedule(self, is_show_schedule, event_slug, organizer_slug, user_email):
    try:
        headers = set_header_token(user_email)
        payload = {'is_show_schedule': is_show_schedule}
        # Send the POST request with the payload and the headers
        ticket_uri = urljoin(
            settings.EVENTYAY_TICKET_BASE_PATH,
            f'api/v1/{organizer_slug}/{event_slug}/schedule-public/',
        )
        response = requests.post(ticket_uri, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        logger.error(
            'Error occurred when triggering hide/unhide schedule for tickets component.'
            'Event: %s, Organizer: %s. Error: %s',
            event_slug,
            organizer_slug,
            e,
        )
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error('Max retries exceeded for sending organizer webhook.')


import io
import importlib
import traceback

from defusedcsv import csv as defcsv
from django.core.files.base import ContentFile


@app.task(
    bind=True,
    name='eventyay.orga.run_csv_export',
    max_retries=2,
    default_retry_delay=30,
    queue='longrunning',
)
def run_csv_export(self, event_id, cached_file_id, form_class_path, options):
    """
    Generates a CSV export in the background and stores it in a CachedFile.
    Triggered by ExportForm.export_data() when export_format == 'csv'.

    Args:
        event_id       : PK of the Event
        cached_file_id : UUID str of the CachedFile that will hold the result
        form_class_path: dotted path e.g. 'eventyay.orga.forms.speaker.SpeakerExportForm'
        options        : cleaned_data dict — fields, questions (pks), delimiter
    """
    from eventyay.base.models import CachedFile, Event
    from django_scopes import scope

    try:
        event = Event.objects.get(pk=event_id)
        cf    = CachedFile.objects.get(pk=cached_file_id)

        # Rebuild the form instance so we can call its helpers (get_queryset, etc.)
        module_path, class_name = form_class_path.rsplit('.', 1)
        FormClass = getattr(importlib.import_module(module_path), class_name)
        form = FormClass(event=event)
        form.cleaned_data = options        # already validated; skip re-validation

        fields       = options.get('fields', [])
        question_pks = options.get('questions', [])
        delimiter    = '\n' if options.get('delimiter') == 'newline' else ', '
        questions    = [q for q in form.questions if q.pk in question_pks]
        queryset     = form.get_queryset()

        import tempfile

        temp_file = tempfile.NamedTemporaryFile(mode='w+', newline='', delete=False)
        writer = defcsv.writer(temp_file)
        header_written = False

        with scope(event=event):
            for obj in queryset.iterator(chunk_size=200):
                row = {}

                code = getattr(obj, 'code', None)
                if code:
                    row['ID'] = code

                prepare = getattr(form, '_prepare_object_data', None)
                if prepare:
                    obj = prepare(obj)

                for field in fields:
                    value = form.get_object_attribute(obj, field)
                    if isinstance(value, list):
                        value = delimiter.join(str(v) for v in value if v is not None)
                    row[str(form.fields[field].label)] = value

                for question in questions:
                    answer = form.get_answer(question, obj)
                    row[str(question.question)] = answer.answer_string if answer else None

                if hasattr(form, 'get_additional_data'):
                    row.update(form.get_additional_data(obj))

                if not header_written:
                    writer.writerow(list(row.keys()))
                    header_written = True

                writer.writerow(['' if v is None else v for v in row.values()])

        # Persist the finished file into the CachedFile record
        temp_file.flush()
        temp_file.seek(0)

        cf.file.save(
            f'{cached_file_id}.csv',
            ContentFile(temp_file.read().encode('utf-8')) 
        )

        temp_file.close()
        cf.save()

    except Exception as exc:
        logger.error('CSV export failed for CachedFile %s:\n%s', cached_file_id, traceback.format_exc())
        raise self.retry(exc=exc)