import logging

import django_redis
from django.conf import settings
from django.core import cache
from django.db import DatabaseError
from django.http import HttpResponse
from redis.exceptions import RedisError

from eventyay.base.models import User
from eventyay.base.operational_logging import OUTCOME_FAILURE, logger_extra


logger = logging.getLogger('eventyay.core')


def check_dependencies() -> str | None:
    """Probe backend dependencies without emitting endpoint health-alert logs."""
    try:
        User.objects.exists()
    except DatabaseError:
        return 'db_unavailable'

    if settings.HAS_REDIS:
        try:
            redis = django_redis.get_redis_connection('redis')
            redis.set('_healthcheck', 1)
            if not redis.exists('_healthcheck'):
                return 'redis_unavailable'
        except RedisError:
            return 'redis_unavailable'

    try:
        cache.cache.set('_healthcheck', '1')
        if cache.cache.get('_healthcheck') != '1':
            return 'cache_unavailable'
    except Exception:
        return 'cache_unavailable'

    if (settings.CELERY_BROKER_URL or '').startswith('redis') and settings.HAS_REDIS:
        try:
            django_redis.get_redis_connection('redis').ping()
        except Exception:
            return 'queue_unavailable'
    return None


def healthcheck(request):
    """Expose dependency readiness with the existing response and alert contract."""
    error_code = check_dependencies()
    if error_code:
        logger.error('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code=error_code))
        messages = {
            'db_unavailable': 'Database not available.',
            'redis_unavailable': 'Redis not available.',
            'cache_unavailable': 'Cache not available.',
            'queue_unavailable': 'Queue not available.',
        }
        return HttpResponse(messages[error_code], status=503)
    return HttpResponse()
