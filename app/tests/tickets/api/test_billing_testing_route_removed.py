"""Regression tests for the removal of the unauthenticated billing trigger endpoint.

``/api/v1/billing-testing/<task>`` was served by a plain ``django.views.View`` with no
authentication, permission check or throttle, and it invoked the billing Celery tasks as
ordinary functions rather than with ``.delay()``. An anonymous caller could therefore run
``process_auto_billing_charge`` (which confirms Stripe PaymentIntents against organizers'
stored payment methods), mass-mail invoice PDFs, and create billing rows, synchronously
inside a web worker.

The route and its view are gone. These tests keep them gone.
"""

import importlib

import pytest
from django.test import Client
from django.urls import NoReverseMatch, Resolver404, resolve, reverse


BILLING_TASKS = [
    'invoice-collect',
    'invoice-notification',
    'invoice-charge',
    'invoice-retry',
    'invoice-warning',
]


@pytest.mark.parametrize('task', BILLING_TASKS)
def test_billing_testing_path_does_not_resolve(task):
    with pytest.raises(Resolver404):
        resolve(f'/api/v1/billing-testing/{task}')


def test_billing_testing_route_name_is_not_registered():
    with pytest.raises(NoReverseMatch):
        reverse('api-v1:billing-testing', kwargs={'task': 'invoice-charge'})


@pytest.mark.django_db
def test_billing_testing_charge_endpoint_is_not_reachable_anonymously():
    """The Stripe-charging branch must not answer an unauthenticated request."""
    response = Client().get('/api/v1/billing-testing/invoice-charge')
    assert response.status_code == 404


def test_billing_preview_module_no_longer_exists():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('eventyay.eventyay_common.views.billing')
