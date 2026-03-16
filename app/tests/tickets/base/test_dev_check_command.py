from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from eventyay.base.management.commands.dev_check import Command


@pytest.mark.django_db
def test_dev_check_all_pass(monkeypatch):
    monkeypatch.setattr(Command, 'check_database', lambda self: (True, '', ''))
    monkeypatch.setattr(Command, 'check_redis', lambda self: (True, '', ''))
    monkeypatch.setattr(Command, 'check_api', lambda self: (True, '', ''))
    monkeypatch.setattr(Command, 'check_static_files', lambda self: (True, '', ''))

    out = StringIO()
    call_command('dev_check', stdout=out)
    output = out.getvalue()

    assert 'Development Environment Validation' in output
    assert 'Database: PASS' in output
    assert 'Redis: PASS' in output
    assert 'Django API: PASS' in output
    assert 'Static Files: PASS' in output


@pytest.mark.django_db
def test_dev_check_raises_on_failure(monkeypatch):
    monkeypatch.setattr(
        Command,
        'check_database',
        lambda self: (False, 'cannot connect', 'Run database migrations: python manage.py migrate'),
    )
    monkeypatch.setattr(Command, 'check_redis', lambda self: (True, '', ''))
    monkeypatch.setattr(Command, 'check_api', lambda self: (True, '', ''))
    monkeypatch.setattr(Command, 'check_static_files', lambda self: (True, '', ''))

    out = StringIO()
    with pytest.raises(CommandError):
        call_command('dev_check', stdout=out)

    output = out.getvalue()
    assert 'Database: FAIL' in output
    assert 'Reason: cannot connect' in output
    assert 'Hint: Run database migrations: python manage.py migrate' in output
