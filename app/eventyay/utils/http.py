import requests
import logging

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

def safe_get(url, **kwargs):
    try:
        return requests.get(url, timeout=DEFAULT_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error(f"GET request failed: {url} | Error: {e}")
        raise


def safe_post(url, **kwargs):
    try:
        return requests.post(url, timeout=DEFAULT_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error(f"POST request failed: {url} | Error: {e}")
        raise


def safe_put(url, **kwargs):
    try:
        return requests.put(url, timeout=DEFAULT_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error(f"PUT request failed: {url} | Error: {e}")
        raise


def safe_delete(url, **kwargs):
    try:
        return requests.delete(url, timeout=DEFAULT_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error(f"DELETE request failed: {url} | Error: {e}")
        raise