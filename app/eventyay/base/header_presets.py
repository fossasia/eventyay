import random
from contextlib import suppress
from django.core.cache import cache
from django.db.utils import OperationalError, ProgrammingError
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

PRESET_PREFIX = 'preset:'
CACHE_KEY_ACTIVE_PRESETS = 'eventyay_active_header_presets'
CACHE_TIMEOUT = 300  # 5 minutes


def invalidate_preset_cache():
    """Invalidate cached header presets after admin modifications."""
    cache.delete(CACHE_KEY_ACTIVE_PRESETS)


def get_active_presets():
    """Return all active presets from the database, cached for performance."""
    presets = cache.get(CACHE_KEY_ACTIVE_PRESETS)
    if presets is None:
        try:
            from eventyay.base.models.event_header_preset import EventHeaderPreset
            presets = list(
                EventHeaderPreset.objects.filter(is_active=True)
                .select_related('category')
                .order_by('category_id', 'id')
            )
            cache.set(CACHE_KEY_ACTIVE_PRESETS, presets, CACHE_TIMEOUT)
        except (OperationalError, ProgrammingError):
            presets = []
    return presets


def get_active_categories():
    """Return category tuples (category_id_str, localized_name) for categories with active presets."""
    presets = get_active_presets()
    seen = {}
    for p in presets:
        if p.category_id and p.category_id not in seen:
            seen[p.category_id] = p.category.name
    result = [('all', _('All'))]
    for cat_id, cat_name in seen.items():
        result.append((str(cat_id), str(cat_name)))
    return result


def get_preset_by_id():
    """Return a dictionary of {str(preset.id): preset} for all active presets."""
    return {str(preset.id): preset for preset in get_active_presets()}


def get_random_preset_id():
    """Return a random active preset ID as a string, or '' if no active presets exist."""
    presets = get_active_presets()
    if not presets:
        return ''
    return str(random.choice(presets).id)


def resolve_preset_to_url(preset_id: str):
    """Given a preset ID (integer database ID or legacy slug), return the image URL."""
    if not preset_id:
        return None
    raw_id = str(preset_id).strip()
    if raw_id.startswith(PRESET_PREFIX):
        raw_id = raw_id[len(PRESET_PREFIX):]

    preset_map = get_preset_by_id()
    preset = preset_map.get(raw_id)
    from django.core.files.storage import default_storage

    if preset and preset.image:
        with suppress(ValueError, AttributeError, OSError):
            return default_storage.url(preset.image.name)

    from django.db.models import Q
    from eventyay.base.models.event_header_preset import EventHeaderPreset
    fallback = None
    if raw_id.isdigit():
        fallback = EventHeaderPreset.objects.filter(pk=int(raw_id)).first()
    else:
        # Backwards compatibility: match legacy preset slug by name or filename
        slug_name = raw_id.replace('-', ' ')
        fallback = EventHeaderPreset.objects.filter(
            Q(name__icontains=slug_name) | Q(image__icontains=raw_id)
        ).first()

    if fallback and fallback.image:
        with suppress(ValueError, AttributeError, OSError):
            return default_storage.url(fallback.image.name)

    # Legacy static fallback if preset was stored as a static asset identifier
    if not raw_id.isdigit():
        legacy_filename = raw_id if raw_id.endswith('.jpg') else f'{raw_id}.jpg'
        return static(f'eventyay-common/images/header_presets/{legacy_filename}')

    # Final fallback to first active preset if available
    active_presets = get_active_presets()
    if active_presets and active_presets[0].image:
        with suppress(ValueError, AttributeError, OSError):
            return default_storage.url(active_presets[0].image.name)

    return None


def resolve_preset_thumbnail_url(preset_id: str):
    """Given a preset ID, return the storage URL for the thumbnail image."""
    if not preset_id:
        return None
    raw_id = str(preset_id).strip()
    if raw_id.startswith(PRESET_PREFIX):
        raw_id = raw_id[len(PRESET_PREFIX):]

    preset_map = get_preset_by_id()
    preset = preset_map.get(raw_id)
    from django.core.files.storage import default_storage

    if preset:
        if preset.thumbnail:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(preset.thumbnail.name)
        if preset.image:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(preset.image.name)

    from django.db.models import Q
    from eventyay.base.models.event_header_preset import EventHeaderPreset
    fallback = None
    if raw_id.isdigit():
        fallback = EventHeaderPreset.objects.filter(pk=int(raw_id)).first()
    else:
        slug_name = raw_id.replace('-', ' ')
        fallback = EventHeaderPreset.objects.filter(
            Q(name__icontains=slug_name) | Q(image__icontains=raw_id)
        ).first()

    if fallback:
        if fallback.thumbnail:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(fallback.thumbnail.name)
        if fallback.image:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(fallback.image.name)

    if not raw_id.isdigit():
        legacy_filename = raw_id if raw_id.endswith('.jpg') else f'{raw_id}.jpg'
        return static(f'eventyay-common/images/header_presets/thumbs/{legacy_filename}')

    active_presets = get_active_presets()
    if active_presets:
        first = active_presets[0]
        if first.thumbnail:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(first.thumbnail.name)
        if first.image:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(first.image.name)

    return None


def is_preset_value(raw):
    """Check if a settings value or path is a preset reference."""
    return isinstance(raw, str) and raw.startswith(PRESET_PREFIX)


def extract_preset_id(raw):
    """Extract the preset ID from a 'preset:<id>' string."""
    if is_preset_value(raw):
        return raw[len(PRESET_PREFIX):]
    return None
