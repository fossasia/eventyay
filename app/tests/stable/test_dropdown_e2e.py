import pytest
import sys

# Shim for cgi module which is removed in Python 3.13 but used by dependencies (vat_moss)
try:
    import cgi
except ImportError:
    import types
    sys.modules['cgi'] = types.ModuleType('cgi')

from django_scopes import scope
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

def open_dropdown_and_get_handle(selenium, wait, dropdown_id):
    """
    Helper to locate a dropdown by ID, click its summary to open it,
    and return the dropdown element.
    """
    dropdown = wait.until(EC.presence_of_element_located((By.ID, dropdown_id)))
    summary = dropdown.find_element(By.TAG_NAME, "summary")
    summary.click()
    assert dropdown.get_attribute("open") is not None, f"Dropdown {dropdown_id} should be open after click"
    return dropdown

@pytest.mark.django_db
@pytest.mark.selenium
def test_dropdown_close_outside_click(live_server, logged_in_client, event):
    """
    Test that clicking outside the user dropdown closes it.
    """
    selenium = logged_in_client
    with scope(event=event):
        selenium.get(live_server.url + f"/orga/event/{event.slug}/")
    
    wait = WebDriverWait(selenium, 10)
    user_dropdown = open_dropdown_and_get_handle(selenium, wait, "user-dropdown-label")
    
    # Click outside (e.g., on the body/footer)
    main_container = selenium.find_element(By.ID, "main-container")
    main_container.click()
    
    # Assert closed with explicit wait
    wait.until(lambda d: user_dropdown.get_attribute("open") is None)

@pytest.mark.django_db
@pytest.mark.selenium
def test_dropdown_close_escape_key(live_server, logged_in_client, event):
    """
    Test that pressing Escape closes the user dropdown.
    """
    selenium = logged_in_client
    with scope(event=event):
        selenium.get(live_server.url + f"/orga/event/{event.slug}/")
    
    wait = WebDriverWait(selenium, 10)
    user_dropdown = open_dropdown_and_get_handle(selenium, wait, "user-dropdown-label")
    
    # Press Escape
    selenium.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    
    # Assert closed with explicit wait
    wait.until(lambda d: user_dropdown.get_attribute("open") is None)

@pytest.mark.django_db
@pytest.mark.selenium
def test_language_dropdown_close_outside_click(live_server, logged_in_client, event):
    """
    Test that clicking outside the language dropdown closes it.
    """
    # Ensure event has multiple locales so the dropdown appears
    with scope(event=event):
        event.locales = ["en", "de"]
        event.save()
    
    selenium = logged_in_client
    with scope(event=event):
        selenium.get(live_server.url + f"/orga/event/{event.slug}/")
    
    wait = WebDriverWait(selenium, 10)
    # The language dropdown ID is usually 'locale-dropdown-label' based on templates
    lang_dropdown = open_dropdown_and_get_handle(selenium, wait, "locale-dropdown-label")
    
    # Click outside
    main_container = selenium.find_element(By.ID, "main-container")
    main_container.click()
    
    # Assert closed
    wait.until(lambda d: lang_dropdown.get_attribute("open") is None)

@pytest.mark.django_db
@pytest.mark.selenium
def test_dropdown_stays_open_on_inside_click(live_server, logged_in_client, event):
    """
    Test that clicking inside the dropdown does NOT close it.
    """
    selenium = logged_in_client
    with scope(event=event):
        selenium.get(live_server.url + f"/orga/event/{event.slug}/")
    
    wait = WebDriverWait(selenium, 10)
    user_dropdown = open_dropdown_and_get_handle(selenium, wait, "user-dropdown-label")
    
    # Click an element inside the dropdown content
    # We can try clicking the dropdown content container itself or a link inside
    dropdown_content = user_dropdown.find_element(By.CLASS_NAME, "dropdown-content")
    dropdown_content.click()
    
    # Assert still open
    assert user_dropdown.get_attribute("open") is not None, "Dropdown should remain open after inside click"

