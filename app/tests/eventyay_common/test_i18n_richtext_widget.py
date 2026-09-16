from django import forms

from eventyay.common.forms.widgets import I18nEmailEditorWidget, I18nRichTextWidget


def test_i18n_richtext_editor_widget_wraps_each_locale():
    field = forms.CharField()
    widget = I18nRichTextWidget(locales=['en', 'de'], field=field)
    html = widget.render('field', None, attrs={'id': 'id_field'})

    assert 'data-tiptap-wrapper="true"' in html
    assert 'tiptap-wrapper' in html
    assert 'data-tiptap-profile="richtext"' in html
    assert html.count('data-tiptap-wrapper="true"') == 2


def test_i18n_email_editor_widget_wraps_each_locale():
    field = forms.CharField()
    widget = I18nEmailEditorWidget(locales=['en'], field=field)
    html = widget.render('field', None, attrs={'id': 'id_email'})

    assert 'data-tiptap-wrapper="true"' in html
    assert 'data-email-editor="true"' in html
    assert 'data-tiptap-profile="email"' in html
