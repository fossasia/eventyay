import json
import re
from collections import OrderedDict
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.common.urls import is_http_url, normalize_url_scheme


def _badge_svg(letter: str) -> str:
    return (
        '<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
        '<rect x="1" y="1" width="30" height="30" rx="7" fill="currentColor"></rect>'
        f'<text x="16" y="21" text-anchor="middle" font-size="14" '
        'font-family="Arial, sans-serif" font-weight="700" fill="#ffffff">'
        f'{letter}</text></svg>'
    )


@dataclass(frozen=True)
class SocialLinkSpec:
    key: str
    label: object
    prefix: str
    color: str
    icon_class: str = ''
    icon_svg: str = ''


SOCIAL_LINK_SPECS = OrderedDict(
    (
        spec.key,
        spec,
    )
    for spec in (
        SocialLinkSpec(
            key='website',
            label=_('Website'),
            prefix='https://',
            color='#555555',
            icon_class='fa-globe',
        ),
        SocialLinkSpec(
            key='facebook',
            label=_('Facebook'),
            prefix='https://facebook.com/',
            color='#1877f2',
            icon_class='fa-facebook',
        ),
        SocialLinkSpec(
            key='flickr',
            label=_('Flickr'),
            prefix='https://flickr.com/',
            color='#ff0084',
            icon_class='fa-flickr',
        ),
        SocialLinkSpec(
            key='github',
            label=_('GitHub'),
            prefix='https://github.com/',
            color='#24292f',
            icon_class='fa-github',
        ),
        SocialLinkSpec(
            key='gitlab',
            label=_('GitLab'),
            prefix='https://gitlab.com/',
            color='#fc6d26',
            icon_class='fa-gitlab',
        ),
        SocialLinkSpec(
            key='gitter',
            label=_('Gitter'),
            prefix='https://gitter.im/',
            color='#ed1965',
            icon_svg=_badge_svg('G'),
        ),
        SocialLinkSpec(
            key='google_groups',
            label=_('Google Groups'),
            prefix='https://groups.google.com/g/',
            color='#4285f4',
            icon_class='fa-google',
        ),
        SocialLinkSpec(
            key='instagram',
            label=_('Instagram'),
            prefix='https://instagram.com/',
            color='#e4405f',
            icon_class='fa-instagram',
        ),
        SocialLinkSpec(
            key='linkedin',
            label=_('LinkedIn'),
            prefix='https://linkedin.com/in/',
            color='#0a66c2',
            icon_class='fa-linkedin',
        ),
        SocialLinkSpec(
            key='mastodon',
            label=_('Mastodon'),
            prefix='https://mastodon.social/@',
            color='#6364ff',
            icon_svg=_badge_svg('M'),
        ),
        SocialLinkSpec(
            key='patreon',
            label=_('Patreon'),
            prefix='https://patreon.com/',
            color='#ff424d',
            icon_svg=_badge_svg('P'),
        ),
        SocialLinkSpec(
            key='telegram',
            label=_('Telegram'),
            prefix='https://t.me/',
            color='#26a5e4',
            icon_class='fa-telegram',
        ),
        SocialLinkSpec(
            key='vimeo',
            label=_('Vimeo'),
            prefix='https://vimeo.com/',
            color='#1ab7ea',
            icon_class='fa-vimeo',
        ),
        SocialLinkSpec(
            key='vk',
            label=_('VK'),
            prefix='https://vk.com/',
            color='#0077ff',
            icon_class='fa-vk',
        ),
        SocialLinkSpec(
            key='weibo',
            label=_('Weibo'),
            prefix='https://weibo.com/',
            color='#e6162d',
            icon_class='fa-weibo',
        ),
        SocialLinkSpec(
            key='x',
            label=_('X'),
            prefix='https://x.com/',
            color='#111111',
            icon_svg=_badge_svg('X'),
        ),
        SocialLinkSpec(
            key='xing',
            label=_('Xing'),
            prefix='https://xing.com/profile/',
            color='#006567',
            icon_class='fa-xing',
        ),
        SocialLinkSpec(
            key='youtube',
            label=_('YouTube'),
            prefix='https://youtube.com/',
            color='#ff0000',
            icon_class='fa-youtube-play',
        ),
    )
)

SOCIAL_LINK_CHOICES = tuple((spec.key, spec.label) for spec in SOCIAL_LINK_SPECS.values())


def get_social_link_spec(key: str) -> SocialLinkSpec:
    return SOCIAL_LINK_SPECS[key]


def social_link_prefixes() -> dict[str, str]:
    return {key: spec.prefix for key, spec in SOCIAL_LINK_SPECS.items()}


def build_social_link_url(network: str, value: str) -> str:
    value = (value or '').strip()
    if not value:
        return ''

    if '://' in value:
        normalized = normalize_url_scheme(value)
        if not is_http_url(normalized):
            raise ValidationError(_('Please enter a valid http or https URL.'))
        return normalized

    prefix = get_social_link_spec(network).prefix
    if prefix.endswith('@') and value.startswith('@'):
        value = value[1:]
    else:
        value = value.lstrip('/')
    return normalize_url_scheme(f'{prefix}{value}')


def get_social_link_value(url: str, network: str) -> str:
    url = (url or '').strip()
    if not url:
        return ''

    normalized = normalize_url_scheme(url)
    prefix = get_social_link_spec(network).prefix
    if normalized.lower().startswith(prefix.lower()):
        return normalized[len(prefix) :]
    return url


def resolve_social_network(name: str) -> str | None:
    key = re.sub(r'[\s-]+', '_', (name or '').strip().lower()).strip('_')
    if key in SOCIAL_LINK_SPECS:
        return key
    needle = (name or '').strip().casefold()
    if not needle:
        return None
    for spec in SOCIAL_LINK_SPECS.values():
        if str(spec.label).casefold() == needle:
            return spec.key
    return None


def infer_social_network(url: str) -> str | None:
    normalized = normalize_url_scheme(url or '').lower()
    if not normalized:
        return None
    for key, spec in SOCIAL_LINK_SPECS.items():
        if key == 'website':
            continue
        prefix = spec.prefix.lower()
        if prefix and normalized.startswith(prefix):
            return key
    if normalized.startswith(('http://', 'https://')):
        return 'website'
    return None


def format_social_links_for_csv(links) -> str:
    pairs: list[tuple[str, str]] = []
    for link in links:
        network = getattr(link, 'network', None)
        url = getattr(link, 'url', None)
        if not network or not url:
            continue
        pairs.append((str(network), str(url)))
    if not pairs:
        return ''
    if any(';' in url for _, url in pairs):
        return json.dumps([{'network': network, 'url': url} for network, url in pairs])
    return '; '.join(f'{network}: {url}' for network, url in pairs)


def parse_social_links_from_csv(text: str) -> list[tuple[str, str]]:
    raw = (text or '').strip()
    if not raw:
        return []
    parsed = _parse_social_links_json(raw)
    if parsed is not None:
        return parsed
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for chunk in re.split(r'[;\n]+', raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        network = None
        url = chunk
        if ':' in chunk:
            label, remainder = chunk.split(':', 1)
            resolved = resolve_social_network(label)
            if resolved and remainder.strip():
                network = resolved
                url = remainder.strip()
        if not network:
            network = infer_social_network(chunk)
        if not network:
            continue
        try:
            normalized_url = build_social_link_url(network, url)
        except ValidationError:
            continue
        if not normalized_url:
            continue
        identity = (network, normalized_url)
        if identity in seen:
            continue
        seen.add(identity)
        pairs.append(identity)
    return pairs


def _parse_social_links_json(raw: str) -> list[tuple[str, str]] | None:
    if not raw.startswith(('[', '{')):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    items = data if isinstance(data, list) else [data]
    pairs: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        network = resolve_social_network(str(item.get('key') or item.get('network') or ''))
        url = str(item.get('url') or '').strip()
        if not network or not url:
            continue
        try:
            normalized_url = build_social_link_url(network, url)
        except ValidationError:
            continue
        if normalized_url:
            pairs.append((network, normalized_url))
    return pairs


def serialize_social_link(link) -> dict:
    spec = get_social_link_spec(link.network)
    icon_svg = spec.icon_svg
    if not icon_svg:
        # Schedule web component has no Font Awesome; always ship an SVG fallback.
        letter = str(spec.label)[:1].upper() or '?'
        icon_svg = _badge_svg(letter)
    return {
        'key': spec.key,
        'label': str(spec.label),
        'url': link.url,
        'icon_class': spec.icon_class,
        'icon_svg': icon_svg,
        'color': spec.color,
    }
