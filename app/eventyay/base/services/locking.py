import logging
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now

from eventyay.base.models import EventLock

logger = logging.getLogger('pretix.base.locking')
LOCK_TIMEOUT = 120


class NoLockManager:
    def __init__(self):
        pass

    def __enter__(self):
        return now()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False


class LockManager:
    def __init__(self, event, blocking=False, blocking_timeout=None):
        self.event = event
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout

    def __enter__(self):
        lock_event(self.event, blocking=self.blocking, blocking_timeout=self.blocking_timeout)
        return now()

    def __exit__(self, exc_type, exc_val, exc_tb):
        release_event(self.event)
        if exc_type is not None:
            return False


class LockTimeoutException(Exception):  # NOQA: N818
    pass


class LockReleaseException(Exception):  # NOQA: N818
    pass


def lock_event(event, blocking=False, blocking_timeout=None):
    """
    Issue a lock on this event so nobody can book tickets for this event until
    you release the lock. Will retry 5 times on failure unless *blocking* is
    enabled.

    :raises LockTimeoutException: if the event is locked every time we try
                                  to obtain the lock
    """
    if hasattr(event, '_lock') and event._lock:
        return True

    if settings.HAS_REDIS:
        return lock_event_redis(event, blocking=blocking, blocking_timeout=blocking_timeout)
    else:
        return lock_event_db(event, blocking=blocking, blocking_timeout=blocking_timeout)


def release_event(event):
    """
    Release a lock placed by :py:meth:`lock()`. If the parameter force is not set to ``True``,
    the lock will only be released if it was issued in _this_ python
    representation of the database object.

    :raises LockReleaseException: if we do not own the lock
    """
    if not hasattr(event, '_lock') or not event._lock:
        raise LockReleaseException('Lock is not owned by this thread')
    if settings.HAS_REDIS:
        return release_event_redis(event)
    else:
        return release_event_db(event)


def lock_event_db(event, blocking=False, blocking_timeout=None):
    deadline = time.monotonic() + blocking_timeout if blocking and blocking_timeout else None
    while True:
        retries = 5
        for i in range(retries):
            with transaction.atomic():
                dt = now()
                l, created = EventLock.objects.get_or_create(event=event.id)
                if created:
                    event._lock = l
                    return True
                elif l.date < now() - timedelta(seconds=LOCK_TIMEOUT):
                    newtoken = str(uuid.uuid4())
                    updated = EventLock.objects.filter(event=event.id, token=l.token).update(
                        date=dt, token=newtoken
                    )
                    if updated:
                        l.token = newtoken
                        event._lock = l
                        return True
            time.sleep(2**i / 100)
        if not blocking or deadline is None or time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    raise LockTimeoutException()


@transaction.atomic
def release_event_db(event):
    if not hasattr(event, '_lock') or not event._lock:
        raise LockReleaseException('Lock is not owned by this thread')
    try:
        lock = EventLock.objects.get(event=event.id, token=event._lock.token)
        lock.delete()
        event._lock = None
    except EventLock.DoesNotExist:
        raise LockReleaseException('Lock is no longer owned by this thread')


def redis_lock_from_event(event):
    from django_redis import get_redis_connection
    from redis.lock import Lock

    if not hasattr(event, '_lock') or not event._lock:
        rc = get_redis_connection('redis')
        event._lock = Lock(redis=rc, name='pretix_event_%s' % event.id, timeout=LOCK_TIMEOUT)
    return event._lock


def lock_event_redis(event, blocking=False, blocking_timeout=None):
    from redis.exceptions import RedisError

    lock = redis_lock_from_event(event)
    if blocking and blocking_timeout:
        try:
            if lock.acquire(blocking=True, blocking_timeout=blocking_timeout):
                return True
        except RedisError:
            logger.exception('Error locking an event')
            raise LockTimeoutException()
        raise LockTimeoutException()

    retries = 5
    for i in range(retries):
        try:
            if lock.acquire(False):
                return True
        except RedisError:
            logger.exception('Error locking an event')
            raise LockTimeoutException()
        time.sleep(2**i / 100)
    raise LockTimeoutException()


def release_event_redis(event):
    from redis import RedisError

    lock = redis_lock_from_event(event)
    try:
        lock.release()
    except RedisError:
        logger.exception('Error releasing an event lock')
        raise LockTimeoutException()
    event._lock = None
