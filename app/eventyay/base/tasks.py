"""
Celery task imports for autodiscovery.

This module imports all Celery tasks from the services package so they can be
registered with the Celery worker via autodiscover_tasks().
"""

from eventyay.base.services import (  # noqa: F401
    cancelevent,
    cart,
    export,
    invoices,
    mail,
    notifications,
    orderimport,
    orders,
    shredder,
    telemetry,
    tickets,
    update_check,
    waitinglist,
)

