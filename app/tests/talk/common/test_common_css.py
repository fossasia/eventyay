from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError

from eventyay.common.text.css import validate_css


@pytest.fixture
def valid_css():
    return """
body {
  background-color: #000;
  display: none;
}
.some-descriptor {
  /* Dotted borders are IN! */
  border-style: dotted dashed solid double;  /* more commenting */
  BORDER-color: red green blue yellow;
  object-fit: cover;
}
#best-descriptor {
  border: 5px solid red;
}
@media print {
  #best-descriptor {
    border: 5px solid blue;
  }
}
"""


@pytest.fixture
def invalid_css(valid_css):
    return (
        valid_css
        + """
a.other-descriptor {
    content: url("https://malicious.site.com");
}
"""
    )


def test_valid_css(valid_css):
    assert validate_css(valid_css) == valid_css


def test_invalid_css(invalid_css):
    with pytest.raises(ValidationError):
        validate_css(invalid_css)


def test_contact_organizer_button_css_rules():
    css_path = finders.find('common/css/_contact_modal.css')
    assert css_path is not None
    css_content = Path(css_path).read_text(encoding='utf-8')

    # Base styling uses event-themed link color
    assert '.contact-organizer-btn' in css_content
    assert 'footer .contact-organizer-btn' in css_content
    assert 'color: var(--color-primary-text, var(--color-primary, inherit));' in css_content
    assert 'display: inline;' in css_content

    # Hover styling
    hover_color = 'color: var(--color-primary-text-dark, var(--color-primary-hover, var(--color-primary, inherit)));'
    assert '.contact-organizer-btn:hover' in css_content
    assert 'footer .contact-organizer-btn:hover' in css_content
    assert hover_color in css_content
    assert 'text-decoration: underline;' in css_content

    # Focus styling preserves keyboard outline for accessibility
    assert '.contact-organizer-btn:focus' in css_content
    assert 'footer .contact-organizer-btn:focus' in css_content
    assert 'outline: 2px solid var(--color-primary, currentColor);' in css_content
    assert 'outline-offset: 2px;' in css_content

    # Non-visible focus suppresses outline only when :focus-visible is supported
    assert '.contact-organizer-btn:focus:not(:focus-visible)' in css_content
    assert 'footer .contact-organizer-btn:focus:not(:focus-visible)' in css_content

    # Focus-visible styling
    assert '.contact-organizer-btn:focus-visible' in css_content
    assert 'footer .contact-organizer-btn:focus-visible' in css_content

    # Active styling
    assert '.contact-organizer-btn:active' in css_content
    assert 'footer .contact-organizer-btn:active' in css_content
    assert 'color: var(--color-primary-text-dark, var(--color-primary, inherit));' in css_content
