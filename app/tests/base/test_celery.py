from celery.app.utils import find_app

from eventyay.celery import app as celery_compat_app
from eventyay.celery_app import app


def test_celery_entrypoints_export_same_app():
    assert celery_compat_app is app
    assert find_app('eventyay') is app
