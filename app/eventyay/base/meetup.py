from decimal import Decimal
from urllib.parse import urljoin

from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from i18nfield.strings import LazyI18nString

EVENT_TYPE_SETTING = 'event_type'
MEETUP_EVENT_TYPE = 'meetup'
MEETUP_VIDEO_ACTIVE_SETTING = 'meetup_video_active'

DEFAULT_ROOM_NAME = 'Main Room'
DEFAULT_PRODUCT_NAME = 'RSVP Ticket'
DEFAULT_QUOTA_NAME = 'RSVP'

VIDEO_TYPE_YOUTUBE = 'youtube'
VIDEO_TYPE_HLS = 'hls'
VIDEO_TYPE_IFRAME = 'iframe'

VIDEO_TYPE_CHOICES = [
    ('', _('No video stream')),
    (VIDEO_TYPE_YOUTUBE, _('YouTube')),
    (VIDEO_TYPE_HLS, _('HLS stream')),
    (VIDEO_TYPE_IFRAME, _('Embed URL / iframe')),
]

VIDEO_MODULES = {
    VIDEO_TYPE_YOUTUBE: ('livestream.youtube', 'ytid'),
    VIDEO_TYPE_HLS: ('livestream.native', 'hls_url'),
    VIDEO_TYPE_IFRAME: ('livestream.iframe', 'url'),
}

VIDEO_TYPES_BY_MODULE = {
    module_type: (video_type, config_key) for video_type, (module_type, config_key) in VIDEO_MODULES.items()
}

URL_VIDEO_TYPES = (VIDEO_TYPE_HLS, VIDEO_TYPE_IFRAME)

LIVESTREAM_MODULE_PREFIX = 'livestream.'

VIDEO_SETTINGS_KEYS = (
    'venueless_url',
    'venueless_issuer',
    'venueless_audience',
    'venueless_secret',
)


def is_meetup_event(event) -> bool:
    if event is None:
        return False
    return event.settings.get(EVENT_TYPE_SETTING) == MEETUP_EVENT_TYPE


def get_video_module_config(video_type, video_url):
    if not video_type or video_type not in VIDEO_MODULES:
        return []
    module_type, config_key = VIDEO_MODULES[video_type]
    return [{'type': module_type, 'config': {config_key: video_url}}]


def get_video_config_from_modules(module_config) -> dict:
    try:
        entry = (module_config or [])[0]
        module_type = entry.get('type')
        config = entry.get('config') or {}
    except (IndexError, AttributeError, KeyError, TypeError):
        return {}
    if module_type not in VIDEO_TYPES_BY_MODULE:
        return {}
    video_type, config_key = VIDEO_TYPES_BY_MODULE[module_type]
    return {'video_type': video_type, 'video_url': config.get(config_key, '')}


def _is_video_module(module) -> bool:
    module_type = (module or {}).get('type', '') or ''
    return module_type.startswith(LIVESTREAM_MODULE_PREFIX)


def has_video_stream(event) -> bool:
    with scope(event=event):
        return any(
            _is_video_module(module)
            for room in event.rooms.filter(deleted=False)
            for module in room.module_config or []
        )


def get_main_room(event):
    from eventyay.base.models.room import Room

    with scope(event=event):
        return Room.objects.filter(event=event, deleted=False).first()


def get_video_config_initial(event) -> dict:
    room = get_main_room(event)
    if not room:
        return {}
    return get_video_config_from_modules(room.module_config)


def sync_meetup_room(event, module_config):
    from eventyay.base.models.room import Room

    with scope(event=event):
        room = Room.objects.filter(event=event, deleted=False).first()
        if room is None:
            locale = getattr(event, 'locale', 'en') or 'en'
            room = Room(
                event=event,
                name=LazyI18nString({locale: DEFAULT_ROOM_NAME}),
                deleted=False,
            )
        room.module_config = module_config
        room.save()
        return room


def build_video_form_fields(type_help_text=None) -> dict:
    return {
        'video_type': forms.ChoiceField(
            choices=VIDEO_TYPE_CHOICES,
            required=False,
            label=_('Video stream type'),
            help_text=type_help_text or _('Configure a live video stream for this meetup.'),
        ),
        'video_url': forms.CharField(
            required=False,
            max_length=255,
            label=_('Video URL / stream identifier'),
            help_text=_('YouTube video URL, HLS stream URL, or embed URL.'),
        ),
    }


def validate_video_fields(video_type, video_url) -> dict:
    errors = {}
    if video_type and not video_url:
        errors['video_url'] = _('A URL is required when a video type is selected.')
    if video_url and not video_type:
        errors['video_type'] = _('A video type is required when a URL is provided.')
    if video_url and video_type in URL_VIDEO_TYPES:
        try:
            URLValidator()(video_url)
        except ValidationError:
            errors['video_url'] = _('Enter a valid URL.')
    return errors


def add_video_field_errors(form, video_type, video_url):
    for field, message in validate_video_fields(video_type, video_url).items():
        form.add_error(field, message)


def apply_video_configuration(event, video_type, video_url):
    module_config = get_video_module_config(video_type, video_url)
    event.settings.set(MEETUP_VIDEO_ACTIVE_SETTING, bool(module_config))
    sync_meetup_room(event, module_config)
    return module_config


def _has_video_credentials(event) -> bool:
    return all(event.settings.get(key) for key in VIDEO_SETTINGS_KEYS)


def _jwt_config(event) -> dict:
    config = event.config or {}
    if not config.get('JWT_secrets'):
        config['JWT_secrets'] = [
            {
                'issuer': 'any',
                'audience': 'eventyay',
                'secret': get_random_string(length=64),
            }
        ]
        event.config = config
        event.save(update_fields=['config'])
    return event.config['JWT_secrets'][0]


def build_video_base_url(event, request=None) -> str:
    if request is not None:
        scheme = 'https' if request.is_secure() else 'http'
        return f'{scheme}://{request.get_host()}{event.urls.video_base}'
    site_url = getattr(django_settings, 'SITE_URL', 'http://localhost:8000')
    return urljoin(site_url, event.urls.video_base)


def _write_video_credentials(event, request=None):
    jwt_config = _jwt_config(event)
    event.settings.set('venueless_secret', jwt_config['secret'])
    event.settings.set('venueless_issuer', jwt_config['issuer'])
    event.settings.set('venueless_audience', jwt_config['audience'])
    event.settings.set('venueless_all_products', True)
    event.settings.set('venueless_show_public_link', True)
    event.settings.set('venueless_url', build_video_base_url(event, request))


def ensure_video_credentials(event, request=None, force=False) -> bool:
    from eventyay.base.models import Event

    if not force and _has_video_credentials(event):
        return False

    if force:
        _write_video_credentials(event, request)
        return True

    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        if _has_video_credentials(locked_event):
            return False
        _write_video_credentials(locked_event, request)
        locked_event.settings.flush()
    event.settings.flush()
    return True


def ensure_rsvp_product(event):
    """
    Ensure an active admission product and quota exist for a meetup event.

    Note: Product and Quota models in Eventyay are scoped by organizer
    (`event__organizer`) in the ORM, so this helper establishes organizer
    scope internally. Callers should not wrap calls to this helper in
    redundant `scope(organizer=...)` blocks.
    """
    from eventyay.base.models import Quota
    from eventyay.base.models.product import Product

    locale = getattr(event, 'locale', 'en') or 'en'
    with scope(organizer=event.organizer):
        product = event.products.filter(admission=True, active=True).first()
        if product is None:
            product = Product(
                event=event,
                name=LazyI18nString({locale: DEFAULT_PRODUCT_NAME}),
                default_price=Decimal('0.00'),
                admission=True,
                active=True,
            )
            product.save()

        quota = event.quotas.first()
        if quota is None:
            quota = Quota(event=event, name=DEFAULT_QUOTA_NAME, size=None)
            quota.save()
        quota.products.add(product)
        return product, quota


def get_rsvp_product_and_quota(event):
    """
    Retrieve the active RSVP product and associated quota for a meetup event.

    Note: Product and Quota models in Eventyay are scoped by organizer
    (`event__organizer`) in the ORM, so this helper establishes organizer
    scope internally. Callers should not wrap calls to this helper in
    redundant `scope(organizer=...)` blocks.
    """
    with scope(organizer=event.organizer):
        product = event.products.filter(admission=True, active=True).first()
        if product is None:
            return None, None
        quota = product.quotas.first()
        return product, quota


def provision_meetup_event(event, video_type='', video_url='', request=None):
    event.settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)

    event.live = True
    event.tickets_published = True
    event.save(update_fields=['live', 'tickets_published'])

    ensure_video_credentials(event, request=request, force=True)
    apply_video_configuration(event, video_type, video_url)
    ensure_rsvp_product(event)

    event.log_action(
        'eventyay.event.meetup.created',
        data={'video_type': video_type, 'video_url': video_url},
    )
