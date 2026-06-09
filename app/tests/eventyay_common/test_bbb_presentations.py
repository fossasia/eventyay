from django.test import override_settings

from eventyay.base.services.bbb import (
    get_absolute_presentation_url,
    get_presentation_xml,
)


@override_settings(SITE_URL="https://eventyay.example/")
def test_relative_presentation_url_is_made_absolute():
    assert (
        get_absolute_presentation_url("/media/pub/1/presentation.pdf")
        == "https://eventyay.example/media/pub/1/presentation.pdf"
    )


@override_settings(SITE_URL="https://eventyay.example/")
def test_absolute_presentation_url_is_unchanged():
    assert (
        get_absolute_presentation_url("https://files.example/presentation.pdf")
        == "https://files.example/presentation.pdf"
    )


@override_settings(SITE_URL="https://eventyay.example/")
def test_presentation_url_whitespace_is_removed():
    assert (
        get_absolute_presentation_url("  https://files.example/presentation.pdf  ")
        == "https://files.example/presentation.pdf"
    )


@override_settings(SITE_URL="https://eventyay.example/")
def test_empty_presentation_url_stays_empty():
    assert get_absolute_presentation_url("  ") == ""


@override_settings(SITE_URL="https://eventyay.example/")
def test_presentation_xml_contains_absolute_escaped_url():
    assert get_presentation_xml("/media/pub/presentation.pdf?download=1&token=abc") == (
        '<modules><module name="presentation">'
        '<document url="https://eventyay.example/media/pub/presentation.pdf?download=1&amp;token=abc" />'
        "</module></modules>"
    )
