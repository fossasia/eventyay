import logging

from django.conf import settings
from django.core import cache
from django.db import DatabaseError
from django.http import HttpResponse

from eventyay.base.operational_logging import OUTCOME_FAILURE, logger_extra

from ..models import User

logger = logging.getLogger('eventyay.core')


def healthcheck(request):
    try:
        User.objects.exists()
    except DatabaseError:
        logger.exception('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='db_unavailable'))
        return HttpResponse('Database not available.', status=503)

    if settings.HAS_REDIS:
        import django_redis
        from redis.exceptions import RedisError

        try:
            redis = django_redis.get_redis_connection('redis')
            redis.set('_healthcheck', 1)
            if not redis.exists('_healthcheck'):
                logger.error('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='redis_unavailable'))
                return HttpResponse('Redis not available.', status=503)
        except RedisError:
            logger.exception('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='redis_unavailable'))
            return HttpResponse('Redis not available.', status=503)

    try:
        cache.cache.set('_healthcheck', '1')
        if not cache.cache.get('_healthcheck') == '1':
            logger.error('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='cache_unavailable'))
            return HttpResponse('Cache not available.', status=503)
    except Exception:
        logger.exception('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='cache_unavailable'))
        return HttpResponse('Cache not available.', status=503)

    broker_url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
    if broker_url.startswith('redis') and settings.HAS_REDIS:
        try:
            import django_redis

            django_redis.get_redis_connection('redis').ping()
        except Exception:
            logger.exception('health.check', extra=logger_extra('core', 'health.check', OUTCOME_FAILURE, error_code='queue_unavailable'))
            return HttpResponse('Queue not available.', status=503)

    return HttpResponse()
