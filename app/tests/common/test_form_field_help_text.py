"""Help text placement in the shared form field template.

Radio button and checkbox lists render their help text above the first option,
every other field type keeps it below the input.
"""

from django import forms

from eventyay.common.forms.renderers import TabularFormRenderer


HELP_TEXT = 'Which best describes your current role?'
CHOICES = (('a', 'Founder'), ('b', 'Student'))


class ChoiceFieldsForm(forms.Form):
    default_renderer = TabularFormRenderer

    radio = forms.ChoiceField(choices=CHOICES, widget=forms.RadioSelect, help_text=HELP_TEXT)
    checkboxes = forms.MultipleChoiceField(choices=CHOICES, widget=forms.CheckboxSelectMultiple, help_text=HELP_TEXT)
    select = forms.ChoiceField(choices=CHOICES, help_text=HELP_TEXT)
    text = forms.CharField(help_text=HELP_TEXT)
    confirmation = forms.BooleanField(help_text=HELP_TEXT)


def render_field(name):
    return str(ChoiceFieldsForm()[name].as_field_group())


def assert_help_text_above_options(html):
    assert html.count(HELP_TEXT) == 1
    assert html.index(HELP_TEXT) < html.index('<input')


def assert_help_text_below_input(html):
    assert html.count(HELP_TEXT) == 1
    assert html.index(HELP_TEXT) > html.index('<input')


def test_radio_button_help_text_is_above_the_options():
    assert_help_text_above_options(render_field('radio'))


def test_checkbox_help_text_is_above_the_options():
    assert_help_text_above_options(render_field('checkboxes'))


def test_select_help_text_stays_below_the_input():
    html = render_field('select')
    assert html.count(HELP_TEXT) == 1
    assert html.index(HELP_TEXT) > html.index('<select')


def test_text_help_text_stays_below_the_input():
    assert_help_text_below_input(render_field('text'))


def test_single_checkbox_help_text_stays_below_the_input():
    assert_help_text_below_input(render_field('confirmation'))
