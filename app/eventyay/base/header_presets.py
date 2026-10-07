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


def _resolve_preset_url(preset_id: str, use_thumbnail=False):
    """Internal helper to resolve a preset to its full or thumbnail URL."""
    if not preset_id:
        return None
        
    raw_id = str(preset_id).strip()
    if raw_id.startswith(PRESET_PREFIX):
        raw_id = raw_id[len(PRESET_PREFIX):]

    preset = get_preset_by_id().get(raw_id)
    
    from django.db.models import Q
    from django.core.files.storage import default_storage
    from eventyay.base.models.event_header_preset import EventHeaderPreset

    if not preset:
        if raw_id.isdigit():
            preset = EventHeaderPreset.objects.filter(pk=int(raw_id)).first()
        else:
            slug_name = raw_id.replace('-', ' ')
            preset = EventHeaderPreset.objects.filter(
                Q(name__icontains=slug_name) | Q(image__icontains=raw_id)
            ).first()

    if preset:
        target_file = preset.thumbnail if use_thumbnail and preset.thumbnail else preset.image
        if target_file:
            with suppress(ValueError, AttributeError, OSError):
                return default_storage.url(target_file.name)

    if not raw_id.isdigit():
        folder = 'thumbs/' if use_thumbnail else ''
        legacy_filename = raw_id if raw_id.endswith('.jpg') else f'{raw_id}.jpg'
        return static(f'eventyay-common/images/header_presets/{folder}{legacy_filename}')

    return None


def resolve_preset_to_url(preset_id: str):
    """Given a preset ID (integer database ID or legacy slug), return the image URL."""
    return _resolve_preset_url(preset_id, use_thumbnail=False)


def resolve_preset_thumbnail_url(preset_id: str):
    """Given a preset ID, return the storage URL for the thumbnail image."""
    return _resolve_preset_url(preset_id, use_thumbnail=True)


def is_preset_value(raw):
    """Check if a settings value or path is a preset reference."""
    return isinstance(raw, str) and raw.startswith(PRESET_PREFIX)


def extract_preset_id(raw):
    """Extract the preset ID from a 'preset:<id>' string."""
    if is_preset_value(raw):
        return raw[len(PRESET_PREFIX):]
    return None
