from eventyay.control.views.admin_views import redact_sensitive_data


def test_redact_sensitive_data_simple():
    data = {"public": "value", "password": "secret_password"}
    redacted = redact_sensitive_data(data)
    assert redacted["public"] == "value"
    assert redacted["password"] == "*****"


def test_redact_sensitive_data_substring():
    data = {
        "client_secret": "sensitive1",
        "JWT_SECRETS": "sensitive2",
        "user_password_hash": "sensitive3",
        "api_key_value": "sensitive4",
        "clientSecret": "sensitive5",
        "mysecretvalue": "sensitive6",
        "dbPassword": "sensitive7",
        "apiKey": "sensitive8",
        "authToken": "sensitive9",
    }
    redacted = redact_sensitive_data(data)
    assert redacted["client_secret"] == "*****"
    assert redacted["JWT_SECRETS"] == "*****"
    assert redacted["user_password_hash"] == "*****"
    assert redacted["api_key_value"] == "*****"
    assert redacted["clientSecret"] == "*****"
    assert redacted["mysecretvalue"] == "*****"
    assert redacted["dbPassword"] == "*****"
    assert redacted["apiKey"] == "*****"
    assert redacted["authToken"] == "*****"


def test_redact_sensitive_data_nested():
    data = {
        "user": {
            "name": "John",
            "credentials": {
                "api_key": "12345",
                "nested": ["item1", {"password": "pwd"}],
            },
        },
        "tags": ["tag1", "tag2"],
    }
    redacted = redact_sensitive_data(data)
    assert redacted["user"]["name"] == "John"
    assert redacted["user"]["credentials"]["api_key"] == "*****"
    assert redacted["user"]["credentials"]["nested"][1]["password"] == "*****"
    assert redacted["tags"] == ["tag1", "tag2"]


def test_redact_sensitive_data_non_dict():
    data = "simple string"
    assert redact_sensitive_data(data) == "simple string"

    data_list = ["a", "b", {"secret": "val"}]
    redacted = redact_sensitive_data(data_list)
    assert redacted[0] == "a"
    assert redacted[2]["secret"] == "*****"
