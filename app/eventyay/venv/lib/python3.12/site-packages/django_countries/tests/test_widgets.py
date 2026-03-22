from unittest import mock
from urllib import parse as urlparse

from django.forms.models import modelform_factory
from django.test import TestCase, override_settings
from django.utils import safestring
from django.utils.html import escape

from django_countries import countries, fields, widgets
from django_countries.conf import settings
from django_countries.tests.models import Person
from django_countries.widgets import CountrySelectWidget


def person_form(widgets=None, **kwargs):
    if widgets is None:
        widgets = {"country": CountrySelectWidget}
    return modelform_factory(Person, fields=["country"], widgets=widgets, **kwargs)


class TestCountrySelectWidget(TestCase):
    def setUp(self):
        del countries.countries

    def tearDown(self):
        del countries.countries

    def test_not_default_widget(self):
        PersonForm = person_form(widgets={})
        widget = PersonForm().fields["country"].widget
        self.assertFalse(isinstance(widget, widgets.CountrySelectWidget))

    def test_render_contains_flag_url(self):
        with self.settings(COUNTRIES_ONLY={"AU": "Desert"}):
            PersonForm = person_form()
            html = PersonForm().as_p()
            self.assertIn(
                escape(
                    urlparse.urljoin(settings.STATIC_URL, settings.COUNTRIES_FLAG_URL)
                ),
                html,
            )

    def test_render(self):
        with self.settings(COUNTRIES_ONLY={"AU": "Desert"}):
            PersonForm = person_form()
            html = PersonForm().as_p()
            self.assertInHTML("""<option value="AU">Desert</option>""", html, count=1)
            self.assertIn(fields.Country("__").flag, html)
            self.assertNotIn(fields.Country("AU").flag, html)

    def test_render_initial(self):
        with self.settings(COUNTRIES_ONLY={"AU": "Desert"}):
            PersonForm = person_form()
            html = PersonForm(initial={"country": "AU"}).as_p()
            self.assertIn(fields.Country("AU").flag, html)
            self.assertNotIn(fields.Country("__").flag, html)

    def test_render_escaping(self):
        output = widgets.CountrySelectWidget().render("test", "<script>")
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)
        self.assertTrue(isinstance(output, safestring.SafeData))

    def test_render_modelform_instance(self):
        person = Person(country="NZ")
        PersonForm = person_form()
        PersonForm(instance=person).as_p()

    def test_required_attribute(self):
        PersonForm = person_form()
        rendered = PersonForm()["country"].as_widget()
        rendered = rendered[: rendered.find(">") + 1]
        self.assertIn("required", rendered)


class TestDefaultSelectWidget(TestCase):
    def setUp(self):
        del countries.countries

    def tearDown(self):
        del countries.countries

    def setup_form(self):
        """
        Setup form for use in tests.

        Note that this isn't in setUp so that we can call it inside of a
        settings override scope.
        """
        self.Form = modelform_factory(Person, fields=["country"])

    def test_is_default_widget(self):
        self.setup_form()

        widget = self.Form().fields["country"].widget
        self.assertNotIsInstance(widget, widgets.CountrySelectWidget)
        self.assertIsInstance(widget, widgets.LazySelect)

    @override_settings(COUNTRIES_ONLY=["NZ", "AU"])
    def test_required_attribute(self):
        self.setup_form()
        rendered = self.Form()["country"].as_widget()
        rendered_first_tag = rendered[: rendered.find(">") + 1]
        self.assertIn("required", rendered_first_tag)

        self.assertHTMLEqual(
            """
            <select name="country" id="id_country" required>
              <option value="" selected>---------</option>
              <option value="AU">Australia</option>
              <option value="NZ">New Zealand</option>
            </select>
            """,
            rendered,
        )

    @override_settings(
        COUNTRIES_FIRST=["NZ"],
        COUNTRIES_ONLY=["NZ", "AU"],
        COUNTRIES_FIRST_BREAK="-----",
    )
    def test_required_attribute_with_countries_first_break(self):
        self.setup_form()
        field = self.Form()["country"]
        rendered = field.as_widget()
        rendered_first_tag = rendered[: rendered.find(">") + 1]
        self.assertIn("required", rendered_first_tag)

        self.assertHTMLEqual(
            """
            <select name="country" id="id_country" required>
                <option value="NZ">New Zealand</option>
                <option value="" selected>-----</option>
                <option value="AU">Australia</option>
            </select>
            """,
            rendered,
        )

    @override_settings(COUNTRIES_ONLY=["NZ", "AU"])
    def test_lazy_select_use_required_attribute_when_hidden(self):
        """
        Test that LazySelect.use_required_attribute returns False for hidden widgets.
        This is defensive code since LazySelect is never actually hidden in practice.
        """
        self.setup_form()
        form = self.Form()
        widget = form.fields["country"].widget

        # Verify it's a LazySelect
        self.assertIsInstance(widget, widgets.LazySelect)

        # Normally, LazySelect.is_hidden is False
        self.assertFalse(widget.is_hidden)
        self.assertTrue(widget.use_required_attribute(form.fields["country"]))

        # Simulate a hidden widget (defensive test)
        # Use PropertyMock to patch the is_hidden property on the class
        with mock.patch.object(
            type(widget), "is_hidden", new_callable=mock.PropertyMock, return_value=True
        ):
            self.assertFalse(widget.use_required_attribute(form.fields["country"]))
