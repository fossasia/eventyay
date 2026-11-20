import kombu

from eventyay.config.settings import increase_redis_db


def test_increase_redis_db_basic():
    assert increase_redis_db("redis://localhost:6379", 1) == "redis://localhost:6379/1"
    assert increase_redis_db("redis://localhost:6379/0", 1) == "redis://localhost:6379/1"
    assert increase_redis_db("redis://localhost:6379/1", 2) == "redis://localhost:6379/3"


def test_increase_redis_db_sanitizes_kombu_incompatible_params():
    url = "redis://127.0.0.1:6379/0?protocol=2"
    sanitized = increase_redis_db(url, 1)
    assert sanitized == "redis://127.0.0.1:6379/1"

    # Verify Kombu Connection accepts the sanitized broker URL without TypeError
    conn = kombu.Connection(sanitized)
    assert conn.port == 6379
    assert conn.virtual_host in ("/1", "1")


def test_increase_redis_db_preserves_kombu_compatible_params():
    url = "redis://127.0.0.1:6379/0?protocol=2&ssl_cert_reqs=none&connect_timeout=10"
    sanitized = increase_redis_db(url, 1)
    assert "protocol" not in sanitized
    assert "ssl_cert_reqs=none" in sanitized
    assert "connect_timeout=10" in sanitized

    conn = kombu.Connection(sanitized)
    assert str(conn.connect_timeout) == "10"


def test_increase_redis_db_preserves_query_when_sanitize_disabled():
    url = "redis://127.0.0.1:6379/0?protocol=2"
    result = increase_redis_db(url, 1, sanitize_broker=False)
    assert result == "redis://127.0.0.1:6379/1?protocol=2"
