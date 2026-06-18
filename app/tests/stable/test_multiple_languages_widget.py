from bs4 import BeautifulSoup
from django import forms

from eventyay.control.forms import MultipleLanguagesWidget


def test_multiple_languages_widget_rendering():
    widget = MultipleLanguagesWidget()
    widget.choices = [
        ('xyz', 'Xyz Language'),
        ('abc', 'Abc Language'),
        ('en', 'English'),
    ]

    html = widget.render('test_locales', ['en', 'xyz'], attrs={'id': 'id_test_locales'})

    assert 'language-grid-widget' in html

    soup = BeautifulSoup(html, 'html.parser')

    checkboxes = soup.find_all('input', type='checkbox', attrs={'name': 'test_locales'})
    assert len(checkboxes) == 3

    values = [cb['value'] for cb in checkboxes]
    assert 'en' in values
    assert 'abc' in values
    assert 'xyz' in values

    assert values[0] == 'en'
    assert values[1] == 'abc'
    assert values[2] == 'xyz'


def test_multiple_languages_widget_shows_required_marker():
    class LanguageForm(forms.Form):
        test_locales = forms.MultipleChoiceField(
            choices=[('en', 'English')],
            widget=MultipleLanguagesWidget,
            required=True,
        )

    soup = BeautifulSoup(str(LanguageForm()['test_locales']), 'html.parser')

    assert soup.select_one('[data-language-grid-required]') is not None
