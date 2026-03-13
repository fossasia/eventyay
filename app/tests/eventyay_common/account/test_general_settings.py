"""
Tests for the general account settings form and view.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()


class GeneralSettingsFormTest(TestCase):
    """Tests for UserSettingsForm in account general settings."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.fullname = 'John Doe'
        self.user.save()
        self.client = Client()
        self.client.login(email='test@example.com', password='testpass123')

    def test_change_fullname_only_no_password_required(self):
        """Test that changing only fullname doesn't require current password."""
        # This was the bug - changing fullname would incorrectly require a password
        response = self.client.post(
            '/account/general-settings/',  # Adjust URL if needed
            {'fullname': 'Jane Doe'},
            follow=True
        )
        # Should succeed without error about needing current password
        self.assertEqual(response.status_code, 200)
        # Check that fullname was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.fullname, 'Jane Doe')

    def test_email_field_not_in_form(self):
        """Test that email field is not in the general settings form."""
        from eventyay.base.forms.user import UserSettingsForm
        
        form = UserSettingsForm(
            user=self.user,
            data={
                'fullname': 'Jane Doe',
            }
        )
        # Email should not be in the form fields
        self.assertNotIn('email', form.fields)

    def test_change_password_requires_old_password(self):
        """Test that changing password still requires current password."""
        form_data = {
            'fullname': self.user.fullname,
            'new_pw': 'newpass123',
            'new_pw_repeat': 'newpass123',
        }
        response = self.client.post(
            '/account/general-settings/',
            form_data,
            follow=True
        )
        # Should fail because old_pw is not provided
        self.assertContains(
            response,
            'Please enter your current password'
        )

    def test_change_password_with_old_password_succeeds(self):
        """Test that providing current password allows password change."""
        form_data = {
            'fullname': self.user.fullname,
            'old_pw': 'testpass123',
            'new_pw': 'newpass123',
            'new_pw_repeat': 'newpass123',
        }
        response = self.client.post(
            '/account/general-settings/',
            form_data,
            follow=True
        )
        # Should succeed
        self.assertContains(response, 'changes have been saved')
