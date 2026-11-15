import ipaddress
import mimetypes
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.timezone import now

from eventyay.base.models.storage_model import StoredFile
from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event
from eventyay.consts import SizeKey


def get_extension_from_response(response):
    content_type = response.headers.get("Content-Type")
    if not content_type:
        return
    content_type = content_type.split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type)
    ext_whitelist = (
        ".png",
        ".jpg",
        ".gif",
        ".jpeg",
        ".webp",
    )
    if extension in ext_whitelist:
        return content_type, extension
    return None, None


def find_data(html, key):
    elements = html.select(f'meta[property="{key}"], meta[name="{key}"]')
    if elements:
        return elements[0].attrs.get("content")


def store_image(response, event):  # TODO deduplicate
    content_type, extension = get_extension_from_response(response)
    if not extension:
        return

    max_size = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_OTHER]
    if not len(response.content) < max_size:
        return

    uid = uuid.uuid4()
    filename = f"{uid}{extension}"
    stored_file = StoredFile.objects.create(
        id=uid,
        event=event,
        date=now(),
        filename=filename,
        type=content_type,
        public=True,
        source_url=response.url[:254],
    )
    stored_file.file.save(filename, ContentFile(response.content))
    return stored_file.file.url


MAX_PREVIEW_REDIRECTS = 3
PREVIEW_DNS_TIMEOUT = 5  # seconds
PREVIEW_HTTP_TIMEOUT = 10  # seconds
# Well-known NAT64 prefix (RFC 6052). Python treats it as global, but on networks with
# NAT64 it reaches the embedded IPv4 address, which can be private.
NAT64_NETWORK = ipaddress.ip_network('64:ff9b::/96')

# getaddrinfo() has no timeout of its own, so it runs in a small pool to bound how long
# a slow resolver can block the worker.
dns_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='preview-dns')


def is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            address = address.ipv4_mapped
        elif address in NAT64_NETWORK:
            address = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return address.is_global and not address.is_multicast


def resolve_public_address(url: str) -> str | None:
    """
    Resolve the host of an http(s) URL and return an address to connect to.

    Link previews are fetched server-side for any URL posted in chat, so the URL is
    refused (``None``) unless its host resolves exclusively to public addresses (SSRF).
    """
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return None
    future = dns_executor.submit(
        socket.getaddrinfo,
        parsed.hostname,
        port or (443 if parsed.scheme == 'https' else 80),
        type=socket.SOCK_STREAM,
    )
    try:
        infos = future.result(timeout=PREVIEW_DNS_TIMEOUT)
    except FuturesTimeoutError:
        future.cancel()
        return None
    except (socket.gaierror, UnicodeError):
        return None
    if not infos:
        return None
    addresses = []
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return None
        if not is_public_address(address):
            return None
        addresses.append(address)
    return str(addresses[0])


class PinnedAddressAdapter(HTTPAdapter):
    """
    Connect to an already validated address instead of resolving the hostname again,
    so the target cannot change between the check and the request (DNS rebinding).
    The original hostname is still used for the Host header, SNI and certificate checks.
    """

    def __init__(self, address: str):
        self.address = address
        super().__init__(max_retries=0)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        netloc = f'[{self.address}]' if ':' in self.address else self.address
        if parsed.port:
            netloc = f'{netloc}:{parsed.port}'
        if parsed.scheme == 'https':
            self.poolmanager.connection_pool_kw['server_hostname'] = parsed.hostname
            self.poolmanager.connection_pool_kw['assert_hostname'] = parsed.hostname
        # Send a copy so the session still sees the original URL (cookies, redirects).
        pinned = request.copy()
        pinned.url = urlunparse(parsed._replace(netloc=netloc))
        pinned.headers['Host'] = parsed.netloc.rpartition('@')[2]
        response = super().send(pinned, **kwargs)
        response.url = request.url
        response.request = request
        return response


def normalize_url(url: str) -> str | None:
    """
    Return the URL as Requests will send it (e.g. IDNA-encoded hostname), so the
    hostname that is validated is the same one that is requested.
    """
    try:
        return requests.Request('GET', url).prepare().url
    except (requests.RequestException, ValueError):
        return None


def fetch_pinned(session: requests.Session, url: str, address: str) -> requests.Response:
    adapter = PinnedAddressAdapter(address)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session.get(url, timeout=PREVIEW_HTTP_TIMEOUT, allow_redirects=False)  # TODO: user agent


def retrieve_url(url):
    """
    Fetch a URL for a link preview.

    Every hop, including redirects, is resolved and checked with
    ``resolve_public_address`` and then requested at exactly that address.
    One session is used for all hops so cookies set before a redirect are kept.
    """
    with requests.Session() as session:
        # Environment proxies would connect by hostname and bypass the pinned address.
        session.trust_env = False
        for _ in range(MAX_PREVIEW_REDIRECTS + 1):
            url = normalize_url(url)
            address = resolve_public_address(url) if url else None
            if not address:
                log_event('video', 'connection.get', OUTCOME_FAILURE, error_code='blocked_url', backend='preview')
                return
            try:
                response = fetch_pinned(session, url, address)
            except requests.RequestException:
                log_event('video', 'connection.get', OUTCOME_FAILURE, error_code='request_error', backend='preview')
                return
            if not response.is_redirect:
                break
            url = urljoin(url, response.headers['Location'])
        else:
            log_event('video', 'connection.get', OUTCOME_FAILURE, error_code='too_many_redirects', backend='preview')
            return
    if response.status_code == 200:
        return response
    if response.status_code >= 500:
        log_event(
            'video',
            'connection.get',
            OUTCOME_FAILURE,
            error_code='http_error',
            status=response.status_code,
            backend='preview',
        )


def fetch_preview_data(url, event):
    """
    Fetches data from an external URL, and handles social media tags or their fallbacks,
    if any. If the URL refers to an image or the social tags include a preview image,
    the image is prefetched.

    The response format is a dictionary, including these keys (all optional):

    - url: Extracted from og:url, falling back to the original URL
    - title: Extracted from og:title, falling back to <title>
    - description: Extracted from og:description, falling back to description
    - format: Extracted from twitter:card, one of "summary", "summary_large_image", "app", or "player"
    - image: a URL, extracted and cached from og:image
    - video: a video URL, extracted from og:video
    """

    response = retrieve_url(url)
    if not response:
        return
    content_type = response.headers.get("Content-Type", "text/html")  # Assume HTML

    if "image/" in content_type:
        image_url = store_image(response, event)
        if image_url:  # We don't store huge images
            return {"image": image_url}

    elif "text/html" in content_type:
        text = response.content.decode()
        header_end = text.find("</head>")
        if not header_end:  # Avoid parsing huge HTML docs for now
            return
        try:
            html = BeautifulSoup(text[: header_end + 7], "html.parser")
        except Exception:  # Ignore faulty websites
            return

        result = {}
        title = find_data(html, "og:title") or find_data(html, "title")
        if not title and html.find("title"):
            title = html.find("title").text
        if title:
            result["title"] = title
        result["description"] = find_data(html, "og:description") or find_data(
            html, "description"
        )
        result["format"] = find_data(html, "twitter:card")
        result["video"] = find_data(html, "og:video")
        result["site_name"] = find_data(html, "og:site-name")

        result = {key: value for key, value in result.items() if value}

        image = find_data(html, "og:image")
        if image:
            response = retrieve_url(image)
            if response:
                image_url = store_image(response, event)
                if image_url:  # We don't store huge images
                    result["image"] = image_url

        if result:
            result["url"] = find_data(html, "og:url") or url

        return result or None
