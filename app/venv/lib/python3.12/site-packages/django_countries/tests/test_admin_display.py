"""Tests for displaying CountryField(multiple=True) in Django admin."""

from django.contrib.admin.utils import display_for_field
from django.test import TestCase

from django_countries.tests import models


class TestMultipleCountryAdminDisplay(TestCase):
    """Test that multiple country fields display correctly in admin."""

    def test_display_for_field_with_list_display(self):
        """
        Test that multiple country fields work in list_display.

        Regression test for #311: TypeError "unhashable type: 'list'"
        when using CountryField(multiple=True) in list_display.
        """
        multi = models.MultiCountry.objects.create(countries="US,CA,MX")
        field = models.MultiCountry._meta.get_field("countries")

        # This should not raise TypeError: unhashable type: 'list'
        # Django's display_for_field expects a displayable value
        result = display_for_field(multi.countries, field, "")

        # Should display something meaningful, not "-" and not crash
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, "-")
        # Should contain country information
        self.assertIn("United States", result)

    def test_display_for_field_readonly(self):
        """
        Test that multiple country fields display correctly when readonly.

        Regression test for #463: CountryField shows up as "-" in admin
        when readonly with multiple=True.
        """
        multi = models.MultiCountry.objects.create(countries="US,CA")
        field = models.MultiCountry._meta.get_field("countries")

        # When field is in readonly_fields, display_for_field is called
        result = display_for_field(multi.countries, field, "-")

        # Should NOT be the empty_value_display (-)
        self.assertNotEqual(result, "-")
        # Should be a string representation
        self.assertIsInstance(result, str)
        # Should contain both countries
        self.assertIn("United States", result)
        self.assertIn("Canada", result)

    def test_display_for_field_empty_countries(self):
        """Test that empty multiple country fields display properly."""
        multi = models.MultiCountry.objects.create(countries="")
        field = models.MultiCountry._meta.get_field("countries")

        result = display_for_field(multi.countries, field, "-")

        # Django 4.2 returns "" for empty string values
        # Django 5.x returns "-" (the empty_value_display)
        # Both behaviors are acceptable for empty fields
        self.assertIn(result, ["", "-"])

    def test_value_from_object_returns_displayable_descriptor(self):
        """
        Test that value_from_object returns a MultipleCountriesDescriptor.

        This is what Django admin uses when accessing field values.
        The descriptor should be list-like but provide proper string display.
        """
        multi = models.MultiCountry.objects.create(countries="NZ,AU")
        field = models.MultiCountry._meta.get_field("countries")

        # value_from_object returns the descriptor
        value = field.value_from_object(multi)

        # Should be iterable like a list
        self.assertEqual(len(value), 2)

        # String representation should show country names, not codes
        str_value = str(value)
        self.assertIn("New Zealand", str_value)
        self.assertIn("Australia", str_value)

        # Should be usable in admin context (hashable would fail, but str works)
        self.assertIsInstance(str_value, str)

    def test_multiple_countries_descriptor_list_behavior(self):
        """Test that MultipleCountriesDescriptor acts like a list."""
        multi = models.MultiCountry.objects.create(countries="NZ,AU,CA")

        # Test iteration
        country_codes = [country.code for country in multi.countries]
        self.assertEqual(country_codes, ["AU", "CA", "NZ"])  # Sorted by default

        # Test indexing
        first_country = multi.countries[0]
        self.assertEqual(first_country.code, "AU")

        # Test length
        self.assertEqual(len(multi.countries), 3)

        # Test boolean (truthy)
        self.assertTrue(bool(multi.countries))

        # Test repr for debugging
        repr_str = repr(multi.countries)
        self.assertIn("Country", repr_str)

    def test_multiple_countries_descriptor_empty_behavior(self):
        """Test MultipleCountriesDescriptor with empty list."""
        multi = models.MultiCountry.objects.create(countries="")

        # Empty string representation
        self.assertEqual(str(multi.countries), "")

        # Empty is falsy
        self.assertFalse(bool(multi.countries))

        # Empty length
        self.assertEqual(len(multi.countries), 0)

    def test_multiple_countries_descriptor_equality(self):
        """Test MultipleCountriesDescriptor equality comparisons."""
        multi1 = models.MultiCountry.objects.create(countries="NZ,AU")
        multi2 = models.MultiCountry.objects.create(countries="NZ,AU")
        multi3 = models.MultiCountry.objects.create(countries="US,CA")

        # Same countries should be equal
        self.assertEqual(multi1.countries, multi2.countries)

        # Different countries should not be equal
        self.assertNotEqual(multi1.countries, multi3.countries)

    def test_single_country_field_flatchoices(self):
        """Test that single (non-multiple) fields still use flatchoices normally."""
        from django_countries.tests.models import Person

        person = Person.objects.create(name="Test", country="US")
        field = Person._meta.get_field("country")

        # Single fields should have flatchoices
        flatchoices = field.flatchoices
        self.assertIsNotNone(flatchoices)

        # display_for_field should work normally for single fields
        result = display_for_field(person.country, field, "-")
        self.assertEqual(result, "United States of America")
