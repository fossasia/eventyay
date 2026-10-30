import pytest
from celery.app.utils import find_app
from fakeredis import FakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from eventyay.celery import app as celery_compat_app
from eventyay.celery_app import app, log_operational_task_failure, record_task_failure, task_failure_count


def test_celery_entrypoints_export_same_app():
    assert celery_compat_app is app
    assert find_app('eventyay') is app


def test_task_failure_count_retains_a_rolling_day(settings, mocker):
    """Deduplicate failures, expire old IDs and count only the latest 24 hours."""
    settings.HAS_REDIS = True
    redis = FakeRedis()
    mocker.patch('eventyay.celery_app.Redis.from_url', return_value=redis)
    clock = mocker.patch('eventyay.celery_app.time')
    clock.time.return_value = 200000
    redis.zadd('eventyay:task-failures', {'old': 113599, 'boundary': 113600, 'recent': 199900})
    assert task_failure_count() == 1
    record_task_failure('same-id')
    record_task_failure('same-id')
    assert task_failure_count() == 2
    assert redis.zcard('eventyay:task-failures') == 2
    assert 0 < redis.ttl('eventyay:task-failures') <= 86400
    clock.time.return_value = 286401
    assert task_failure_count() == 0


def test_task_failure_history_unavailable_without_redis(settings, mocker):
    """Do not present absent monitoring as a measured zero failures."""
    settings.HAS_REDIS = False
    connect = mocker.patch('eventyay.celery_app.Redis.from_url')
    assert task_failure_count() is None
    record_task_failure('task-id')
    connect.assert_not_called()


def test_task_failure_signal_handles_unavailable_history(settings, mocker):
    """A monitoring-store failure must not mask the original worker failure."""
    settings.HAS_REDIS = True
    mocker.patch('eventyay.celery_app.record_task_failure', side_effect=RedisError('Unavailable'))
    mocker.patch('eventyay.celery_app.log_event')
    logged = mocker.patch('eventyay.celery_app.logger.exception')
    log_operational_task_failure(task_id='task-id', exception=ValueError('Invalid task input'))
    logged.assert_called_once()


@pytest.mark.parametrize('error', (RedisConnectionError, RedisTimeoutError))
@pytest.mark.parametrize('during_query', (False, True))
def test_task_failure_count_handles_redis_outage(settings, mocker, error, during_query):
    """Treat connection and query failures as unavailable monitoring data."""
    settings.HAS_REDIS = True
    connect = mocker.patch('eventyay.celery_app.Redis.from_url')
    if during_query:
        connect.return_value.__enter__.return_value.zcount.side_effect = error('Unavailable')
    else:
        connect.side_effect = error('Unavailable')
    warning = mocker.patch('eventyay.celery_app.logger.warning')
    assert task_failure_count() is None
    warning.assert_called_once()
