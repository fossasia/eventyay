import pytest
from unittest.mock import patch
from django.test import RequestFactory, override_settings

from eventyay.control.checkin_app import (
    CHECKIN_APP_PRODUCTION_URL,
    get_eventyay_checkin_app_url,
    is_eventyay_checkin_app_dev,
)


@pytest.mark.parametrize(
    'vite_dev,plugin_dev,dir_exists,expected',
    [
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test_is_eventyay_checkin_app_dev(vite_dev, plugin_dev, dir_exists, expected):
    with override_settings(VITE_DEV_MODE=vite_dev, PLUGIN_DEV_MODE=plugin_dev):
        with patch('pathlib.Path.is_dir', return_value=dir_exists):
            assert is_eventyay_checkin_app_dev() == expected


@pytest.mark.parametrize(
    'is_dev,expected_url',
    [
        (False, CHECKIN_APP_PRODUCTION_URL),
        (True, 'http://testserver:8085/'),
    ],
)
def test_get_eventyay_checkin_app_url(is_dev, expected_url):
    with patch('eventyay.control.checkin_app.is_eventyay_checkin_app_dev', return_value=is_dev):
        req = RequestFactory().get('/')
        assert get_eventyay_checkin_app_url(req) == expected_url

