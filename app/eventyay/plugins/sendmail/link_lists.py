import os
import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils.translation import gettext_lazy as _

from eventyay.base.services.orderimport import parse_csv
from eventyay.plugins.sendmail.models import LINK_LIST_PLACEHOLDER_PREFIX, MailLinkList, MailLinkListRow


LINK_LIST_PLACEHOLDER = re.compile(r'\{(' + LINK_LIST_PLACEHOLDER_PREFIX + r'[a-z0-9_]+)\}')


@dataclass
class ParsedLinkList:
    columns: list
    rows: list = field(default_factory=list)


COLUMN_KEY_MAX_LENGTH = 90


def column_key(header, index):
    key = re.sub(r'[^a-z0-9]+', '_', (header or '').strip().lower()).strip('_')[:COLUMN_KEY_MAX_LENGTH].strip('_')
    return key or f'column_{index + 1}'


def parse_link_list(upload):
    """Read an uploaded CSV whose first row names the columns into placeholder keys and row values."""
    upload.seek(0)
    try:
        reader = parse_csv(upload)
    except UnicodeDecodeError as error:
        raise ValidationError(_('The file could not be read as text: {error}').format(error=error))
    if reader is None or not reader.fieldnames:
        raise ValidationError(_('The file is empty.'))
    keys = []
    for index, header in enumerate(reader.fieldnames):
        key = column_key(header, index)
        while key in keys:
            key = f'{key}_{index + 1}'
        keys.append(key)
    rows = []
    for record in reader.reader:
        cells = [(cell or '').strip() for cell in record]
        rows.append({key: cells[index] if index < len(cells) else '' for index, key in enumerate(keys)})
    if not rows:
        raise ValidationError(_('The file has no rows below the column names.'))
    return ParsedLinkList(columns=keys, rows=rows)


def missing_columns(link_list, parsed):
    """Saved columns of the list that an uploaded file does not have."""
    return [column for column in link_list.columns if column not in parsed.columns]


@transaction.atomic
def add_rows(link_list, rows):
    """Append rows to a list, skipping empty rows and rows the list already holds; returns (added, skipped)."""
    MailLinkList.objects.select_for_update().filter(pk=link_list.pk).first()
    seen = {tuple(sorted(row.items())) for row in link_list.rows.values_list('values', flat=True)}
    position = link_list.rows.aggregate(last=Max('position'))['last'] or 0
    new_rows = []
    skipped = 0
    for row in rows:
        values = {column: (row.get(column) or '').strip() for column in link_list.columns}
        signature = tuple(sorted(values.items()))
        if not any(values.values()) or signature in seen:
            skipped += 1
            continue
        seen.add(signature)
        position += 1
        new_rows.append(MailLinkListRow(link_list=link_list, position=position, values=values))
    MailLinkListRow.objects.bulk_create(new_rows)
    return len(new_rows), skipped


@transaction.atomic
def create_link_list(event, name, parsed, user=None):
    link_list = MailLinkList.objects.create(event=event, name=name, columns=parsed.columns)
    added, skipped = add_rows(link_list, parsed.rows)
    event.log_action(
        'eventyay.sendmail.link_list.created',
        user=user,
        data={'link_list': link_list.pk, 'name': name, 'added': added, 'skipped': skipped},
    )
    return link_list, added, skipped


def default_list_name(upload):
    return os.path.splitext(os.path.basename(getattr(upload, 'name', '') or ''))[0][:190] or str(_('Link list'))


def used_link_list_placeholders(*values):
    """Link list placeholder names used in the given subject and message texts, in every language."""
    used = set()
    for value in values:
        if value is None:
            continue
        data = getattr(value, 'data', value)
        texts = data.values() if isinstance(data, dict) else [data]
        for text in texts:
            used.update(LINK_LIST_PLACEHOLDER.findall((text or '').replace('\\_', '_')))
    return used
