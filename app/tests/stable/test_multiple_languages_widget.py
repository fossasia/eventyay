import pytest
from bs4 import BeautifulSoup

from eventyay.control.forms import MultipleLanguagesWidget


@pytest.mark.django_db
def test_multiple_languages_widget_rendering():
    widget = MultipleLanguagesWidget()
    
    # Dummy choices
    choices = [
        ('xyz', 'Xyz Language'),
        ('abc', 'Abc Language'),
        ('en', 'English'),
    ]
    
    html = widget.render('test_locales', ['en', 'xyz'], attrs={'id': 'id_test_locales'}, choices=choices)
    
    # Assert grid markup is present
    assert 'language-grid-widget' in html
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Assert checkboxes have correct name and value
    checkboxes = soup.find_all('input', type='checkbox', attrs={'name': 'test_locales'})
    assert len(checkboxes) == 3
    
    values = [cb['value'] for cb in checkboxes]
    assert 'en' in values
    assert 'abc' in values
    assert 'xyz' in values
    
    # Assert choices are sorted as expected
    # The widget sorts by (official, incubating, other), then by name
    # 'en' is official, so it should be first. 'abc' and 'xyz' are "other" and should be sorted alphabetically by name
    assert values[0] == 'en'
    assert values[1] == 'abc'
    assert values[2] == 'xyz'
