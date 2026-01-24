"""
Unit tests for User.get_primary_email() method.

Tests the verification-aware fallback logic:
1. Primary verified email → use it
2. First verified email → use it
3. user.email → fallback
4. Empty string → no email available
"""

from django.test import TestCase
from eventyay.base.models import User


class GetPrimaryEmailTestCase(TestCase):
    """Test suite for User.get_primary_email() method."""

    def setUp(self):
        """Create test users for each test case."""
        self.user_with_primary = User.objects.create(
            email='original@example.com',
            fullname='Test User With Primary'
        )
        
        self.user_without_allauth = User.objects.create(
            email='legacy@example.com', 
            fullname='Legacy User'
        )
        
        self.user_no_email = User.objects.create(
            fullname='No Email User'
        )

    def test_primary_verified_email_is_used(self):
        """Test that primary verified email is returned when available."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add primary verified email
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='primary@example.com',
                primary=True,
                verified=True
            )
            
            # Add another verified email
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='secondary@example.com',
                primary=False,
                verified=True
            )
            
            result = self.user_with_primary.get_primary_email()
            self.assertEqual(result, 'primary@example.com')
            
        except ImportError:
            self.skipTest('allauth not available')

    def test_first_verified_email_when_no_primary(self):
        """Test that first verified email is used when no primary exists."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add verified emails without primary flag
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='first@example.com',
                primary=False,
                verified=True
            )
            
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='second@example.com',
                primary=False,
                verified=True
            )
            
            result = self.user_with_primary.get_primary_email()
            # Should return one of the verified emails
            self.assertIn(result, ['first@example.com', 'second@example.com'])
            
        except ImportError:
            self.skipTest('allauth not available')

    def test_fallback_to_user_email_when_primary_unverified(self):
        """Test fallback to user.email when primary email is unverified."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add primary but unverified email
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='unverified@example.com',
                primary=True,
                verified=False
            )
            
            result = self.user_with_primary.get_primary_email()
            self.assertEqual(result, 'original@example.com')  # Falls back to user.email
            
        except ImportError:
            self.skipTest('allauth not available')

    def test_fallback_to_user_email_when_no_verified_emails(self):
        """Test fallback to user.email when no verified emails exist."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add only unverified emails
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='unverified1@example.com',
                primary=False,
                verified=False
            )
            
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='unverified2@example.com',
                primary=False,
                verified=False
            )
            
            result = self.user_with_primary.get_primary_email()
            self.assertEqual(result, 'original@example.com')
            
        except ImportError:
            self.skipTest('allauth not available')

    def test_returns_user_email_when_allauth_not_available(self):
        """Test that user.email is returned when allauth is not available (simulated by no data)."""
        # User without any EmailAddress objects
        result = self.user_without_allauth.get_primary_email()
        self.assertEqual(result, 'legacy@example.com')

    def test_allauth_not_installed_mock(self):
        """Test fallback when allauth.account is not in INSTALLED_APPS."""
        from unittest.mock import patch
        
        # We simulate apps.is_installed returning False
        with patch('django.apps.apps.is_installed') as mock_is_installed:
            mock_is_installed.return_value = False
            
            result = self.user_with_primary.get_primary_email()
            
            # Should receive user.email fallback because app "isn't installed"
            self.assertEqual(result, 'original@example.com')
            
            # Verify is_installed was called
            mock_is_installed.assert_called_with('allauth.account')

    def test_returns_empty_string_when_no_email(self):
        """Test that empty string is returned when user has no email."""
        result = self.user_no_email.get_primary_email()
        self.assertEqual(result, '')

    def test_verified_email_preferred_over_unverified_primary(self):
        """Test that verified non-primary email is preferred over unverified primary."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add unverified primary
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='unverified-primary@example.com',
                primary=True,
                verified=False
            )
            
            # Add verified non-primary
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='verified-secondary@example.com',
                primary=False,
                verified=True
            )
            
            result = self.user_with_primary.get_primary_email()
            # Should prefer verified email over unverified primary
            self.assertEqual(result, 'verified-secondary@example.com')
            
        except ImportError:
            self.skipTest('allauth not available')

    def test_multiple_verified_emails_returns_consistent_result(self):
        """Test that method returns consistent result with multiple verified emails."""
        try:
            from allauth.account.models import EmailAddress
            
            # Add multiple verified emails
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='email1@example.com',
                primary=False,
                verified=True
            )
            
            EmailAddress.objects.create(
                user=self.user_with_primary,
                email='email2@example.com',
                primary=False,
                verified=True
            )
            
            # Call multiple times to ensure consistency
            result1 = self.user_with_primary.get_primary_email()
            result2 = self.user_with_primary.get_primary_email()
            
            self.assertEqual(result1, result2)
            self.assertIn(result1, ['email1@example.com', 'email2@example.com'])
            
        except ImportError:
            self.skipTest('allauth not available')

    def tearDown(self):
        """Clean up test data."""
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.all().delete()
        except ImportError:
            pass
        
        User.objects.all().delete()
