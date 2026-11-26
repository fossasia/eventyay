import kombu

from eventyay.config.settings import increase_redis_db


def test_increase_redis_db_basic():
    assert increase_redis_db("redis://localhost:6379", 1) == "redis://localhost:6379/1"
    assert increase_redis_db("redis://localhost:6379/0", 1) == "redis://localhost:6379/1"
    assert increase_redis_db("redis://localhost:6379/1", 2) == "redis://localhost:6379/3"


def test_increase_redis_db_with_query_db_param():
    # Database specified via query param ?db=5
    assert increase_redis_db("redis://localhost?db=5", 1) == "redis://localhost/6"
    assert increase_redis_db("redis://localhost:6379?db=5", 2) == "redis://localhost:6379/7"
    assert (
        increase_redis_db("redis://localhost?db=5&socket_timeout=5", 2, sanitize_broker=False)
        == "redis://localhost/7?socket_timeout=5"
    )
    # When both path and ?db= are provided, query param takes precedence (matching redis-py)
    assert increase_redis_db("redis://localhost/0?db=1", 1) == "redis://localhost/2"
    assert (
        increase_redis_db("redis://localhost/0?db=1&socket_timeout=5", 2, sanitize_broker=False)
        == "redis://localhost/3?socket_timeout=5"
    )


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
    url = "redis://127.0.0.1:6379/0?protocol=2&socket_timeout=5&socket_connect_timeout=5"
    result = increase_redis_db(url, 2, sanitize_broker=False)
    assert result == "redis://127.0.0.1:6379/2?protocol=2&socket_timeout=5&socket_connect_timeout=5"


def test_increase_redis_db_duplicate_db_params():
    # When duplicate db query parameters exist, select the first nonempty one
    assert increase_redis_db("redis://localhost/0?db=1&db=4", 1) == "redis://localhost/2"
    assert increase_redis_db("redis://localhost?db=&db=3", 1) == "redis://localhost/4"


def test_increase_redis_db_invalid_query_db_falls_back_to_path():
    # If query db is invalid/non-numeric, fall back to path database if present
    assert increase_redis_db("redis://localhost/3?db=invalid", 1) == "redis://localhost/4"
    # If both query and path are non-numeric or missing, default to 0 and increment
    assert increase_redis_db("redis://localhost/invalid?db=invalid", 1) == "redis://localhost/1"


def test_increase_redis_db_excludes_transport_options():
    # transport_options should not be passed in broker URL query
    url = "redis://127.0.0.1:6379/0?transport_options=custom&connect_timeout=10"
    sanitized = increase_redis_db(url, 1)
    assert "transport_options" not in sanitized
    assert "connect_timeout=10" in sanitized

    # When sanitize_broker is False, transport_options is preserved
    unsanitized = increase_redis_db(url, 1, sanitize_broker=False)
    assert "transport_options=custom" in unsanitized


def test_increase_redis_db_preserves_credentials():
    # Query parameters username and password must be preserved for broker authentication
    url = "redis://127.0.0.1:6379/0?username=myuser&password=mypassword&protocol=2"
    sanitized = increase_redis_db(url, 1)
    assert "protocol" not in sanitized
    assert "username=myuser" in sanitized
    assert "password=mypassword" in sanitized
