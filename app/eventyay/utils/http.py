import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


def _safe_request(method, url, **kwargs):
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)

    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException:
        logger.exception(f"{method.upper()} request failed: {url}")
        raise


def safe_get(url, **kwargs):
    return _safe_request("get", url, **kwargs)


def safe_post(url, **kwargs):
    return _safe_request("post", url, **kwargs)


def safe_put(url, **kwargs):
    return _safe_request("put", url, **kwargs)


def safe_delete(url, **kwargs):
    return _safe_request("delete", url, **kwargs)