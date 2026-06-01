import json
import time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from eventyay.base.models import User
from eventyay.control.forms.filter import UserFilterForm


def _make_admin(email='admin@example.com', password='admin_pw_123!'):
    admin = User.objects.create_user(email, password)
    admin.is_staff = True
    admin.is_superuser = True
    admin.save()
    return admin


def _make_user(email='user@example.com', password='user_pw_123!', **kwargs):
    user = User.objects.create_user(email, password)
    for k, v in kwargs.items():
        setattr(user, k, v)
    if kwargs:
        user.save()
    return user


class UserModelFieldsTest(TestCase):

    def test_is_verified_defaults_false(self):
        user = _make_user('v@example.com')
        self.assertFalse(user.is_verified)

    def test_is_spam_defaults_false(self):
        user = _make_user('s@example.com')
        self.assertFalse(user.is_spam)

    def test_can_set_is_verified(self):
        user = _make_user('v2@example.com')
        user.is_verified = True
        user.save(update_fields=['is_verified'])
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_can_set_is_spam(self):
        user = _make_user('s2@example.com')
        user.is_spam = True
        user.save(update_fields=['is_spam'])
        user.refresh_from_db()
        self.assertTrue(user.is_spam)


class SpamLoginBlockingTest(TestCase):

    def setUp(self):
        self.user = _make_user('spam@example.com', 'good_pw_123!')
        self.spam_user = _make_user('markedspam@example.com', 'good_pw_123!', is_spam=True)

    def test_normal_user_can_login(self):
        response = self.client.post(
            reverse('eventyay_common:auth.login'),
            {'email': 'spam@example.com', 'password': 'good_pw_123!'},
        )
        self.assertEqual(response.status_code, 302)

    def test_spam_user_blocked(self):
        response = self.client.post(
            reverse('eventyay_common:auth.login'),
            {'email': 'markedspam@example.com', 'password': 'good_pw_123!'},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertEqual(form.errors.get('__all__').as_data()[0].code, 'spam')

    def test_spam_error_code_in_form(self):
        from django import forms as django_forms
        from eventyay.base.forms.auth import LoginForm

        form = LoginForm.__new__(LoginForm)
        with self.assertRaises(django_forms.ValidationError) as ctx:
            form.confirm_login_allowed(self.spam_user)
        self.assertEqual(ctx.exception.code, 'spam')


class UserFilterFormTest(TestCase):

    def setUp(self):
        self.verified_user = _make_user('v@ex.com', is_verified=True)
        self.unverified_user = _make_user('u@ex.com', is_verified=False)
        self.spam_user = _make_user('sp@ex.com', is_spam=True)
        self.clean_user = _make_user('cl@ex.com', is_spam=False)

    def _filter(self, data):
        form = UserFilterForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        return form.filter_qs(User.objects.all())

    def test_filter_verified_yes(self):
        qs = self._filter({'verified': 'yes'})
        emails = list(qs.values_list('email', flat=True))
        self.assertIn('v@ex.com', emails)
        self.assertNotIn('u@ex.com', emails)

    def test_filter_verified_no(self):
        qs = self._filter({'verified': 'no'})
        emails = list(qs.values_list('email', flat=True))
        self.assertNotIn('v@ex.com', emails)
        self.assertIn('u@ex.com', emails)

    def test_filter_spam_yes(self):
        qs = self._filter({'spam': 'yes'})
        emails = list(qs.values_list('email', flat=True))
        self.assertIn('sp@ex.com', emails)
        self.assertNotIn('cl@ex.com', emails)

    def test_filter_spam_no(self):
        qs = self._filter({'spam': 'no'})
        emails = list(qs.values_list('email', flat=True))
        self.assertNotIn('sp@ex.com', emails)
        self.assertIn('cl@ex.com', emails)

    def test_filter_all_no_filter(self):
        qs = self._filter({})
        self.assertGreaterEqual(qs.count(), 4)


class AdminUserListViewTest(TestCase):

    def setUp(self):
        self.admin = _make_admin()
        self.target_user = _make_user('target@example.com', is_spam=False, is_verified=False)

    def _login_as_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['pretix_auth_login_time'] = int(time.time())
        session['pretix_auth_long_session'] = False
        session.save()

    def test_list_view_requires_staff_session(self):
        regular = _make_user('reg@example.com')
        self.client.force_login(regular)
        response = self.client.get(reverse('eventyay_admin:admin.users'))
        self.assertIn(response.status_code, [301, 302, 403])

    def test_new_columns_present(self):
        self._login_as_admin()
        with patch.object(self.admin.__class__, 'has_active_staff_session', return_value=True):
            response = self.client.get(reverse('eventyay_admin:admin.users'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Member Since', content)
        self.assertIn('Last Accessed', content)
        self.assertIn('Verified', content)
        self.assertIn('Spam', content)
        self.assertIn(reverse('eventyay_admin:admin.users.toggle_verified', kwargs={'id': self.target_user.pk}), content)
        self.assertIn(reverse('eventyay_admin:admin.users.toggle_spam', kwargs={'id': self.target_user.pk}), content)


class UserToggleViewsTest(TestCase):

    def setUp(self):
        self.admin = _make_admin()
        self.target_user = _make_user('toggle@example.com')

    def _post_as_admin(self, url):
        self.client.force_login(self.admin)
        session = self.client.session
        session['pretix_auth_login_time'] = int(time.time())
        session['pretix_auth_long_session'] = False
        session.save()
        with patch.object(self.admin.__class__, 'has_active_staff_session', return_value=True):
            return self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_toggle_verified_flips_field(self):
        self.assertFalse(self.target_user.is_verified)
        response = self._post_as_admin(
            reverse('eventyay_admin:admin.users.toggle_verified', kwargs={'id': self.target_user.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_verified)

    def test_toggle_spam_flips_field(self):
        self.assertFalse(self.target_user.is_spam)
        response = self._post_as_admin(
            reverse('eventyay_admin:admin.users.toggle_spam', kwargs={'id': self.target_user.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_spam)

    def test_toggle_spam_on_admin_is_blocked(self):
        other_admin = _make_admin(email='otheradmin@example.com')
        response = self._post_as_admin(
            reverse('eventyay_admin:admin.users.toggle_spam', kwargs={'id': other_admin.pk})
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('cannot be marked as spam', data['message'])

    def test_toggle_admin_flips_field(self):
        self.assertFalse(self.target_user.is_staff)
        response = self._post_as_admin(
            reverse('eventyay_admin:admin.users.toggle_admin', kwargs={'id': self.target_user.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_staff)

    def test_toggle_requires_admin(self):
        regular = _make_user('reg2@example.com')
        self.client.force_login(regular)
        session = self.client.session
        session['pretix_auth_login_time'] = int(time.time())
        session.save()
        response = self.client.post(
            reverse('eventyay_admin:admin.users.toggle_verified', kwargs={'id': self.target_user.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertIn(response.status_code, [301, 302, 403])
