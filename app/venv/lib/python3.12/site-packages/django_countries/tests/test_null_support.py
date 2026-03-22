"""
Tests for improved null=True support for CountryField.

This addresses PR #453 by properly supporting null=True for single-value
fields (especially useful with unique=True constraints) while keeping
the multiple=True + null=True check.
"""

from django.db import models
from django.test import TestCase
from rest_framework import serializers

from django_countries.fields import Country, CountryField
from django_countries.serializers import CountryFieldMixin
from django_countries.tests.models import AllowNull


class TestNullBehavior(TestCase):
    """Test that null=True fields properly handle NULL values."""

    def test_null_field_returns_country_with_none_code(self):
        """
        When a field has null=True and the database value is NULL,
        the descriptor returns Country(code=None), which is falsy.
        """
        obj = AllowNull.objects.create(country=None)

        # Refresh from database to ensure we're testing descriptor behavior
        obj = AllowNull.objects.get(pk=obj.pk)

        # Should return Country object with code=None
        self.assertIsInstance(obj.country, Country)
        self.assertIsNone(obj.country.code)
        # Should be falsy for boolean checks
        self.assertFalse(obj.country)

    def test_null_field_with_value_returns_country(self):
        """
        When a field has null=True but has a value, should return Country object.
        """
        obj = AllowNull.objects.create(country="NZ")
        obj = AllowNull.objects.get(pk=obj.pk)

        self.assertIsInstance(obj.country, Country)
        self.assertEqual(obj.country.code, "NZ")

    def test_null_field_empty_string_returns_empty_country(self):
        """
        Empty string should return an empty Country (for backward compatibility).
        """
        obj = AllowNull.objects.create(country="")
        obj = AllowNull.objects.get(pk=obj.pk)

        self.assertIsInstance(obj.country, Country)
        self.assertEqual(obj.country.code, "")
        self.assertFalse(obj.country)  # Empty country is falsy

    def test_set_to_none(self):
        """Test setting a null=True field to None."""
        obj = AllowNull.objects.create(country="US")
        obj.country = None
        obj.save()

        obj = AllowNull.objects.get(pk=obj.pk)
        self.assertIsNone(obj.country.code)
        self.assertFalse(obj.country)  # Should be falsy

    def test_nullable_deferred_returns_country_with_none(self):
        """Test that deferred loading also returns Country(code=None)."""
        AllowNull.objects.create(country=None)
        obj = AllowNull.objects.defer("country").get()

        # Should return Country with code=None
        self.assertIsInstance(obj.country, Country)
        self.assertIsNone(obj.country.code)
        self.assertFalse(obj.country)


class TestNullWithUnique(TestCase):
    """
    Test that null=True works correctly with unique=True.

    This is the main use case from PR #453: allowing multiple records
    with "no country selected" when the field has unique=True.
    """

    def setUp(self):
        """Create test model with unique country field."""
        # We can't easily create and migrate models in tests, so we'll
        # test the concept with AllowNull (which doesn't have unique=True)
        # but document the expected behavior
        AllowNull.objects.all().delete()

    def test_multiple_nulls_allowed(self):
        """
        Multiple NULL values should be allowed even without unique constraint.

        With unique=True, this is the critical feature: SQL standard allows
        multiple NULLs in UNIQUE columns because NULL != NULL.
        """
        obj1 = AllowNull.objects.create(country=None)
        obj2 = AllowNull.objects.create(country=None)

        # Both should have Country(code=None)
        country1 = AllowNull.objects.get(pk=obj1.pk).country
        country2 = AllowNull.objects.get(pk=obj2.pk).country
        self.assertIsNone(country1.code)
        self.assertIsNone(country2.code)
        self.assertFalse(country1)
        self.assertFalse(country2)

    def test_multiple_empty_strings_allowed_without_unique(self):
        """
        Without unique constraint, empty strings are also allowed.

        Note: With unique=True, multiple empty strings would violate uniqueness.
        """
        AllowNull.objects.create(country="")
        AllowNull.objects.create(country="")

        # Both should succeed (no unique constraint on AllowNull.country)
        self.assertEqual(AllowNull.objects.filter(country="").count(), 2)


class TestSingleValueNullIsAllowed(TestCase):
    """Test that single-value fields with null=True don't produce errors."""

    def test_single_null_field_no_error(self):
        """CountryField(null=True) should not produce a system check error."""

        class TestModel(models.Model):
            country = CountryField(null=True, blank=True)

            class Meta:
                app_label = "test_null"

        # Get field-specific checks
        field = TestModel._meta.get_field("country")
        errors = field.check()

        # Should have no errors
        self.assertEqual(errors, [])


class TestMultipleNullAllowed(TestCase):
    """Test that multiple=True with null=True now works correctly."""

    def test_multiple_null_no_error(self):
        """
        CountryField(multiple=True, null=True) should now be allowed.

        The descriptor properly handles NULL by returning an empty
        MultipleCountriesDescriptor.
        """

        class MultiNullModel(models.Model):
            countries = CountryField(multiple=True, null=True, blank=True)

            class Meta:
                app_label = "test_null"

        field = MultiNullModel._meta.get_field("countries")
        errors = field.check()

        # Should have no errors
        self.assertEqual(errors, [])

    def test_multiple_null_returns_none(self):
        """
        When multiple=True field has NULL value, descriptor returns None.
        This is explicit and consistent with nullable single fields.
        """
        from django_countries.tests.models import MultiCountry

        # Create object with None (simulating null=True behavior)
        obj = MultiCountry(countries=None)

        # Should return None for NULL value
        result = obj.countries
        self.assertIsNone(result)

    def test_multiple_null_with_values(self):
        """Multiple field should still work normally with actual values."""
        from django_countries.tests.models import MultiCountry

        obj = MultiCountry(countries="NZ,AU")
        self.assertEqual(len(obj.countries), 2)
        self.assertTrue(obj.countries)  # Should be truthy

    def test_multiple_empty_string_vs_null(self):
        """
        Test difference between empty string and NULL for multiple fields.

        Empty string returns an empty MultipleCountriesDescriptor (iterable),
        while NULL returns None (explicit absence of value).
        """
        from django_countries.fields import MultipleCountriesDescriptor
        from django_countries.tests.models import MultiCountry

        # Empty string - returns empty descriptor (iterable)
        obj_empty = MultiCountry(countries="")
        self.assertIsInstance(obj_empty.countries, MultipleCountriesDescriptor)
        self.assertEqual(len(obj_empty.countries), 0)
        self.assertFalse(obj_empty.countries)
        self.assertEqual(list(obj_empty.countries), [])

        # NULL - returns None (must check before iterating)
        obj_null = MultiCountry(countries=None)
        self.assertIsNone(obj_null.countries)

        # Both are falsy, but different types
        self.assertFalse(obj_empty.countries)
        self.assertFalse(obj_null.countries)  # None is falsy


class TestDRFSerializerAllowNull(TestCase):
    """Test that DRF serializer respects allow_null parameter."""

    def test_serializer_allow_null_true(self):
        """
        When allow_null=True, serializer should return None for empty values.
        """

        class TestSerializer(CountryFieldMixin, serializers.ModelSerializer):
            class Meta:
                model = AllowNull
                fields = ("country",)
                extra_kwargs = {"country": {"allow_null": True}}

        obj = AllowNull(country=None)
        serializer = TestSerializer(obj)

        # Should return None when allow_null=True
        self.assertIsNone(serializer.data["country"])

    def test_serializer_infers_allow_null_from_model(self):
        """
        DRF automatically infers allow_null=True from model field's null=True.
        This is the standard DRF behavior and matches user expectations.
        """

        class TestSerializer(CountryFieldMixin, serializers.ModelSerializer):
            class Meta:
                model = AllowNull
                fields = ("country",)

        obj = AllowNull(country=None)
        serializer = TestSerializer(obj)

        # Should return None (inferred allow_null=True from model)
        self.assertIsNone(serializer.data["country"])

    def test_serializer_with_value(self):
        """Serializer should return code when there's a value."""

        class TestSerializer(CountryFieldMixin, serializers.ModelSerializer):
            class Meta:
                model = AllowNull
                fields = ("country",)
                extra_kwargs = {"country": {"allow_null": True}}

        obj = AllowNull(country="US")
        serializer = TestSerializer(obj)

        self.assertEqual(serializer.data["country"], "US")


# Document expected behavior for unique constraints
"""
Expected behavior with unique=True (not tested due to migration limitations):

1. CountryField(unique=True, blank=True) - without null=True:
   - Empty values stored as ''
   - First record with '' succeeds
   - Second record with '' raises IntegrityError (unique violation)
   - Use case fails: can't have multiple "unset" values

2. CountryField(unique=True, null=True, blank=True) - with null=True:
   - Empty values stored as NULL
   - First record with NULL succeeds
   - Second record with NULL succeeds (SQL allows multiple NULLs in unique)
   - Use case succeeds: multiple "unset" values allowed

This is the main benefit of properly supporting null=True.
"""
