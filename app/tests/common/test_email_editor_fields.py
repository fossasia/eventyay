import pytest

from eventyay.common.forms.fields import I18nEmailBodyFormField
from eventyay.common.sanitizers import sanitize_email_html
from i18nfield.strings import LazyI18nString


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('<p>Hello</p>', '<p>Hello</p>'),
        ('<p>Hello</p><script>evil()</script>', '<p>Hello</p>'),
    ],
)
def test_i18n_email_body_form_field_sanitizes(raw, expected):
    field = I18nEmailBodyFormField(locales=['en'], required=False)
    result = field.clean([raw])
    assert isinstance(result, LazyI18nString)
    assert result.data['en'] == expected
    assert sanitize_email_html(result.data['en']) == result.data['en']
