import logging

from django.core.cache import cache
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scopes_disabled
from PIL import UnidentifiedImageError
from requests import get

from eventyay.celery_app import app
from eventyay.common.image import create_thumbnail, get_thumbnail_field_name, is_svg_filename
from eventyay.common.signals import minimum_interval, periodic_task
from eventyay.base.models import SpeakerProfile, User
from eventyay.base.models.auth_token import UserApiToken
from eventyay.base.services.stale_cache import bump_schedule_cache_version_on_commit

logger = logging.getLogger(__name__)


@app.task(name='eventyay.person.gravatar_cache')
def gravatar_cache(person_id: int):
    user = User.objects.filter(pk=person_id, get_gravatar=True).first()

    if not user:
        logger.warning(
            'gravatar_cache() was called for user %s, but user was not found or user has gravatar disabled',
            person_id,
        )
        return

    if not user.gravatar_parameter:
        logger.warning(
            'gravatar_cache() was called for user %s, but user has no valid email for Gravatar; disabling get_gravatar',
            person_id,
        )
        user.get_gravatar = False
        user.save(update_fields=['get_gravatar'])
        return

    response = get(
        f'https://www.gravatar.com/avatar/{user.gravatar_parameter}?s=512',
        timeout=10,
    )

    logger.info('gravatar returned http %s when getting avatar for user %s', response.status_code, user.fullname)

    if 400 <= response.status_code <= 499:
        # avatar not found.
        user.get_gravatar = False
        user.save()
        return
    elif response.status_code != 200:
        return

    with NamedTemporaryFile(delete=True) as tmp_img:
        for chunk in response:
            tmp_img.write(chunk)
        tmp_img.flush()

        content_type = response.headers.get('Content-Type')
        if content_type == 'image/png':
            extension = 'png'
        elif content_type == 'image/gif':
            extension = 'gif'
        else:
            extension = 'jpg'

        user.get_gravatar = False
        user.save()
        user.avatar.save(f'{user.gravatar_parameter}.{extension}', File(tmp_img))

        logger.info('set avatar for user %s to %s', user.fullname, user.avatar.url)

    user.process_image('avatar', generate_thumbnail=True)


AVATAR_THUMB_ENQUEUE_TTL = 60
AVATAR_THUMB_BATCH = 200


def enqueue_missing_avatar_thumbnails(event_id, user_ids):
    """Queue missing avatar thumbs off the request path, at most once per minute per event."""
    ids = list(dict.fromkeys(int(pk) for pk in user_ids if pk))
    if not event_id or not ids:
        return
    lock_key = f'eagenda:enqueue-avatar-thumbs:{event_id}'
    if not cache.add(lock_key, 1, AVATAR_THUMB_ENQUEUE_TTL):
        return
    for offset in range(0, len(ids), AVATAR_THUMB_BATCH):
        ensure_avatar_thumbnails.delay(ids[offset : offset + AVATAR_THUMB_BATCH])


@app.task(name='eventyay.person.ensure_avatar_thumbnails')
def ensure_avatar_thumbnails(user_ids):
    ids = list(dict.fromkeys(int(pk) for pk in (user_ids or []) if pk))[:AVATAR_THUMB_BATCH]
    if not ids:
        return
    created = False
    for user in User.objects.filter(pk__in=ids):
        avatar_name = str(getattr(user.avatar, 'name', '') or '')
        if not avatar_name or avatar_name == 'False':
            continue
        if is_svg_filename(avatar_name):
            continue
        for size in ('tiny', 'default'):
            field_name = get_thumbnail_field_name(user.avatar, size)
            stored = getattr(user, field_name, None)
            if stored and stored.name:
                continue
            try:
                thumbnail = create_thumbnail(user.avatar, size)
            except (OSError, ValueError, UnidentifiedImageError) as exc:
                logger.warning(
                    'Failed to create %s avatar thumbnail for user %s: %s',
                    size,
                    user.pk,
                    exc,
                )
                continue
            if thumbnail:
                created = True
    if created:
        with scopes_disabled():
            event_ids = list(
                SpeakerProfile.objects.filter(user_id__in=ids)
                .values_list('event_id', flat=True)
                .distinct()
            )
        for event_id in event_ids:
            bump_schedule_cache_version_on_commit(event_id)


@receiver(periodic_task)
def refetch_gravatars(sender, **kwargs):
    users_with_gravatar = User.objects.filter(get_gravatar=True)

    for user in users_with_gravatar:
        gravatar_cache.apply_async(args=(user.pk,), ignore_result=True)


@receiver(signal=periodic_task)
@minimum_interval(minutes_after_success=60)
def run_update_check(sender, **kwargs):
    UserApiToken.objects.filter(expires__lt=now()).delete()
