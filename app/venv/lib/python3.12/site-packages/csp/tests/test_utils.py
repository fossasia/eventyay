from django.test.utils import override_settings
from django.utils.functional import lazy

from csp.constants import NONCE, NONE, SELF
from csp.utils import DEFAULT_DIRECTIVES, build_policy, default_config


def policy_eq(a: str, b: str) -> None:
    parts_a = sorted(a.split("; "))
    parts_b = sorted(b.split("; "))
    assert parts_a == parts_b, f"{a!r} != {b!r}"


def literal(s: str) -> str:
    return s


lazy_literal = lazy(literal, str)


def test_default_config_none() -> None:
    assert default_config(None) is None


def test_default_config_empty() -> None:
    # Test `default_config` with an empty dict returns defaults.
    assert default_config({}) == DEFAULT_DIRECTIVES


def test_default_config_drops_unknown() -> None:
    # Test `default_config` drops unknown keys.
    config = {"foo-src": ["example.com"]}
    assert default_config(config) == DEFAULT_DIRECTIVES


def test_default_config() -> None:
    # Test `default_config` keeps config along with defaults.
    config = {"img-src": ["example.com"]}
    assert default_config(config) == {**DEFAULT_DIRECTIVES, **config}


def test_empty_policy() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"default-src": None}})
def test_default_src_none() -> None:
    policy = build_policy()
    policy_eq("", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"default-src": ["example.com", "example2.com"]}})
def test_default_src() -> None:
    policy = build_policy()
    policy_eq("default-src example.com example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"default-src": {"example.com", "example2.com"}}})
def test_default_src_is_set() -> None:
    policy = build_policy()
    policy_eq("default-src example.com example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"script-src": ["example.com"]}})
def test_script_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; script-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"script-src-attr": ["example.com"]}})
def test_script_src_attr() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; script-src-attr example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"script-src-elem": ["example.com"]}})
def test_script_src_elem() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; script-src-elem example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"object-src": ["example.com"]}})
def test_object_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; object-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"prefetch-src": ["example.com"]}})
def test_prefetch_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; prefetch-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"style-src": ["example.com"]}})
def test_style_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; style-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"style-src-attr": ["example.com"]}})
def test_style_src_attr() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; style-src-attr example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"style-src-elem": ["example.com"]}})
def test_style_src_elem() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; style-src-elem example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ["example.com"]}})
def test_img_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; img-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"media-src": ["example.com"]}})
def test_media_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; media-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"frame-src": ["example.com"]}})
def test_frame_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; frame-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"font-src": ["example.com"]}})
def test_font_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; font-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"connect-src": ["example.com"]}})
def test_connect_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; connect-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"sandbox": ["allow-scripts"]}})
def test_sandbox() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; sandbox allow-scripts", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"sandbox": []}})
def test_sandbox_empty() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; sandbox", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"report-uri": "/foo"}})
def test_report_uri() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; report-uri /foo", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"report-uri": lazy_literal("/foo")}})
def test_report_uri_lazy() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; report-uri /foo", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"report-to": "some_endpoint"}})
def test_report_to() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; report-to some_endpoint", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ["example.com"]}})
def test_update_img() -> None:
    policy = build_policy(update={"img-src": "example2.com"})
    policy_eq("default-src 'self'; img-src example.com example2.com", policy)


def test_update_missing_setting() -> None:
    """update should work even if the setting is not defined."""
    policy = build_policy(update={"img-src": "example.com"})
    policy_eq("default-src 'self'; img-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ["example.com"]}})
def test_replace_img() -> None:
    policy = build_policy(replace={"img-src": "example2.com"})
    policy_eq("default-src 'self'; img-src example2.com", policy)


def test_replace_missing_setting() -> None:
    """replace should work even if the setting is not defined."""
    policy = build_policy(replace={"img-src": "example.com"})
    policy_eq("default-src 'self'; img-src example.com", policy)


def test_config() -> None:
    policy = build_policy(config={"default-src": [NONE], "img-src": [SELF]})
    policy_eq("default-src 'none'; img-src 'self'", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ("example.com",)}})
def test_update_string() -> None:
    """
    GitHub issue #40 - given project settings as a tuple, and
    an update/replace with a string, concatenate correctly.
    """
    policy = build_policy(update={"img-src": "example2.com"})
    policy_eq("default-src 'self'; img-src example.com example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ("example.com",)}})
def test_replace_string() -> None:
    """
    Demonstrate that GitHub issue #40 doesn't affect replacements
    """
    policy = build_policy(replace={"img-src": "example2.com"})
    policy_eq("default-src 'self'; img-src example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ("example.com",)}})
def test_update_set() -> None:
    """
    GitHub issue #40 - given project settings as a tuple, and
    an update/replace with a string, concatenate correctly.
    """
    policy = build_policy(update={"img-src": {"example2.com"}})
    policy_eq("default-src 'self'; img-src example.com example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ("example.com",)}})
def test_replace_set() -> None:
    """
    Demonstrate that GitHub issue #40 doesn't affect replacements
    """
    policy = build_policy(replace={"img-src": {"example2.com"}})
    policy_eq("default-src 'self'; img-src example2.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"form-action": ["example.com"]}})
def test_form_action() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; form-action example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"base-uri": ["example.com"]}})
def test_base_uri() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; base-uri example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"child-src": ["example.com"]}})
def test_child_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; child-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"frame-ancestors": ["example.com"]}})
def test_frame_ancestors() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; frame-ancestors example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"navigate-to": ["example.com"]}})
def test_navigate_to() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; navigate-to example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"manifest-src": ["example.com"]}})
def test_manifest_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; manifest-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"worker-src": ["example.com"]}})
def test_worker_src() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; worker-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"plugin-types": ["application/pdf"]}})
def test_plugin_types() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; plugin-types application/pdf", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"require-sri-for": ["script"]}})
def test_require_sri_for() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; require-sri-for script", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"require-trusted-types-for": ["'script'"]}})
def test_require_trusted_types_for() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; require-trusted-types-for 'script'", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"trusted-types": ["strictPolicy", "laxPolicy", "default", "'allow-duplicates'"]}})
def test_trusted_types() -> None:
    policy = build_policy()
    policy_eq(
        "default-src 'self'; trusted-types strictPolicy laxPolicy default 'allow-duplicates'",
        policy,
    )


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"upgrade-insecure-requests": True}})
def test_upgrade_insecure_requests() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; upgrade-insecure-requests", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"block-all-mixed-content": True}})
def test_block_all_mixed_content() -> None:
    policy = build_policy()
    policy_eq("default-src 'self'; block-all-mixed-content", policy)


def test_nonce() -> None:
    policy = build_policy(nonce="abc123")
    policy_eq("default-src 'self' 'nonce-abc123'", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"default-src": [SELF], "script-src": [SELF, NONCE], "style-src": [SELF, NONCE]}})
def test_nonce_in_value() -> None:
    policy = build_policy(nonce="abc123")
    policy_eq(
        "default-src 'self'; script-src 'self' 'nonce-abc123'; style-src 'self' 'nonce-abc123'",
        policy,
    )


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"default-src": [NONCE]}})
def test_only_nonce_in_value() -> None:
    policy = build_policy(nonce="abc123")
    policy_eq("default-src 'nonce-abc123'", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ["example.com", "example.com"]}})
def test_deduplicate_values() -> None:
    """
    GitHub issue #40 - given project settings as a tuple, and
    an update/replace with a string, concatenate correctly.
    """
    policy = build_policy()
    policy_eq("default-src 'self'; img-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ["example.com", "example.com"]}})
def test_deduplicate_values_update() -> None:
    """
    GitHub issue #40 - given project settings as a tuple, and
    an update/replace with a string, concatenate correctly.
    """
    policy = build_policy(update={"img-src": "example.com"})
    policy_eq("default-src 'self'; img-src example.com", policy)


@override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {"img-src": ("example.com",)}})
def test_deduplicate_values_replace() -> None:
    """
    Demonstrate that GitHub issue #40 doesn't affect replacements
    """
    policy = build_policy(replace={"img-src": ["example2.com", "example2.com"]})
    policy_eq("default-src 'self'; img-src example2.com", policy)


def test_boolean_directives() -> None:
    for directive in ["upgrade-insecure-requests", "block-all-mixed-content"]:
        with override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {directive: True}}):
            policy = build_policy()
            policy_eq(f"default-src 'self'; {directive}", policy)
        with override_settings(CONTENT_SECURITY_POLICY={"DIRECTIVES": {directive: False}}):
            policy = build_policy()
            policy_eq("default-src 'self'", policy)
