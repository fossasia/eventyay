"""
Tests for Wikimedia user utilities.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from eventyay.person.utils import is_wikimedia_user

User = get_user_model()


class WikimediaUserUtilsTests(TestCase):
    """Test utilities for identifying Wikimedia OAuth users."""

    def test_is_wikimedia_user_true(self):
        """Wikimedia users correctly identified."""
        user = User.objects.create_user(
            email='test@example.com',
            wikimedia_username='testuser',
            is_wikimedia_user=True
        )
        self.assertTrue(is_wikimedia_user(user))

    def test_is_wikimedia_user_false(self):
        """Regular users not identified as Wikimedia users."""
        user = User.objects.create_user(email='test@example.com')
        self.assertFalse(is_wikimedia_user(user))

    def test_is_wikimedia_user_no_email(self):
        """Wikimedia users can have no email."""
        user = User.objects.create_user(
            email=None,
            wikimedia_username='testuser',
            is_wikimedia_user=True
        )
        self.assertTrue(is_wikimedia_user(user))
        self.assertIsNone(user.email)

    def test_is_wikimedia_user_unauthenticated(self):
        """Unauthenticated users are not Wikimedia users."""
        user = User.objects.create_user(
            email='test@example.com',
            wikimedia_username='testuser',
            is_wikimedia_user=True
        )
        user.is_authenticated = False
        self.assertFalse(is_wikimedia_user(user))
