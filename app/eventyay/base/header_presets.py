import random
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

PRESET_PREFIX = 'preset:'

PRESET_CATEGORIES = [
    ('all', _('All')),
    ('abstract', _('Abstract')),
    ('gradients', _('Gradients')),
    ('tech', _('Tech')),
    ('social', _('Social')),
]

HEADER_IMAGE_PRESETS = [
    {
        'id': 'abstract-waves',
        'name': _('Abstract Waves'),
        'category': 'abstract',
        'image': 'eventyay-common/images/header_presets/abstract-waves.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/abstract-waves.jpg',
    },
    {
        'id': 'abstract-spheres',
        'name': _('Abstract Spheres'),
        'category': 'abstract',
        'image': 'eventyay-common/images/header_presets/abstract-spheres.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/abstract-spheres.jpg',
    },
    {
        'id': 'gradient-sunset',
        'name': _('Sunset Glow'),
        'category': 'gradients',
        'image': 'eventyay-common/images/header_presets/gradient-sunset.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/gradient-sunset.jpg',
    },
    {
        'id': 'gradient-ocean',
        'name': _('Ocean Breeze'),
        'category': 'gradients',
        'image': 'eventyay-common/images/header_presets/gradient-ocean.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/gradient-ocean.jpg',
    },
    {
        'id': 'tech-circuit',
        'name': _('Digital Network'),
        'category': 'tech',
        'image': 'eventyay-common/images/header_presets/tech-circuit.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/tech-circuit.jpg',
    },
    {
        'id': 'tech-mesh',
        'name': _('Geometric Mesh'),
        'category': 'tech',
        'image': 'eventyay-common/images/header_presets/tech-mesh.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/tech-mesh.jpg',
    },
    {
        'id': 'social-confetti',
        'name': _('Festive Celebration'),
        'category': 'social',
        'image': 'eventyay-common/images/header_presets/social-confetti.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/social-confetti.jpg',
    },
    {
        'id': 'social-gathering',
        'name': _('Community Meetup'),
        'category': 'social',
        'image': 'eventyay-common/images/header_presets/social-gathering.jpg',
        'thumbnail': 'eventyay-common/images/header_presets/thumbs/social-gathering.jpg',
    },
]

PRESET_BY_ID = {preset['id']: preset for preset in HEADER_IMAGE_PRESETS}


def get_random_preset_id():
    """Return a random preset ID for auto-selection on form load."""
    if not HEADER_IMAGE_PRESETS:
        return ''
    return random.choice(HEADER_IMAGE_PRESETS)['id']


def resolve_preset_to_static_url(preset_id: str):
    """Given a preset ID, return the Django static URL for the full-size image."""
    preset = PRESET_BY_ID.get(preset_id)
    if preset and preset.get('image'):
        return static(preset['image'])
    return None


def resolve_preset_thumbnail_url(preset_id: str):
    """Given a preset ID, return the Django static URL for the thumbnail image."""
    preset = PRESET_BY_ID.get(preset_id)
    if preset and preset.get('thumbnail'):
        return static(preset['thumbnail'])
    return None


def is_preset_value(raw):
    """Check if a settings value or path is a preset reference."""
    return isinstance(raw, str) and raw.startswith(PRESET_PREFIX)


def extract_preset_id(raw):
    """Extract the preset ID from a 'preset:<id>' string."""
    if is_preset_value(raw):
        return raw[len(PRESET_PREFIX):]
    return None
