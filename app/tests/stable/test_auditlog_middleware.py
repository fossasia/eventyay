import json

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from eventyay.base.models.auth import StaffSession, StaffSessionAuditLog, User
from eventyay.control.middleware import AuditLogMiddleware, is_sensitive_key


class AuditLogMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user('admin@example.com', 'password')
        self.user.is_staff = True
        self.user.save()
        self.session = SessionStore()
        self.session.create()
        self.staff_session = StaffSession.objects.create(
            user=self.user,
            session_key=self.session.session_key,
        )

    def _get_request(self, method='POST', path='/control/', data=None, content_type='multipart/form-data'):
        if method == 'POST':
            if content_type == 'application/json':
                request = self.factory.post(path, data=json.dumps(data) if data else '', content_type=content_type)
            else:
                request = self.factory.post(path, data=data)
        else:
            request = self.factory.get(path, data=data)

        request.user = self.user
        request.session = self.session
        return request

    def test_is_sensitive_key_detection(self):
        sensitive_keys = [
            'password',
            'password_1',
            'api_token',
            'secret_key',
            'turnstile_SECRET',
            'csrfmiddlewaretoken',
            'api_key',
            'private_key',
            'access_key',
            'key',
            'key_id',
            'client_credentials',
            'webhook_signature',
            'cvv',
            'cvc',
            'card_number',
        ]
        non_sensitive_keys = [
            'normal_field',
            'keynote',
            'keynote_speaker',
            'keyboard',
            'author',
            'authority',
            'search',
            'email',
            'name',
        ]
        for key in sensitive_keys:
            self.assertTrue(is_sensitive_key(key), f"Expected '{key}' to be detected as sensitive")
        for key in non_sensitive_keys:
            self.assertFalse(is_sensitive_key(key), f"Expected '{key}' not to be detected as sensitive")

    def test_post_data_masking_querydict(self):
        request = self._get_request(data={
            'normal_field': 'value',
            'keynote_topic': 'Keynote Speech',
            'keyboard_layout': 'QWERTY',
            'password_1': 'secret123',
            'api_token': 'abc',
            'secret_key': 'def',
            'api_key': 'xyz',
            'turnstile_SECRET': 'ghi',
            'csrfmiddlewaretoken': 'token123',
            'client_credentials': 'confidential',
        })

        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)

        post_data = json.loads(log.post_data)
        # Normal fields and fields containing 'key' as part of an ordinary word must NOT be masked
        self.assertEqual(post_data['normal_field'], ['value'])
        self.assertEqual(post_data['keynote_topic'], ['Keynote Speech'])
        self.assertEqual(post_data['keyboard_layout'], ['QWERTY'])

        # Sensitive keys MUST be masked
        self.assertEqual(post_data['password_1'], ['***'])
        self.assertEqual(post_data['api_token'], ['***'])
        self.assertEqual(post_data['secret_key'], ['***'])
        self.assertEqual(post_data['api_key'], ['***'])
        self.assertEqual(post_data['turnstile_SECRET'], ['***'])
        self.assertEqual(post_data['csrfmiddlewaretoken'], ['***'])
        self.assertEqual(post_data['client_credentials'], ['***'])

    def test_post_data_masking_json(self):
        request = self._get_request(data={
            'nested': {
                'normal_field': 'value',
                'keynote': 'Keynote Speaker Info',
                'password_1': 'secret123',
            },
            'list': [
                {'api_token': 'abc', 'key': 'secret_key_val'}
            ]
        }, content_type='application/json')

        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)

        post_data = json.loads(log.post_data)
        self.assertEqual(post_data['nested']['normal_field'], 'value')
        self.assertEqual(post_data['nested']['keynote'], 'Keynote Speaker Info')
        self.assertEqual(post_data['nested']['password_1'], '***')
        self.assertEqual(post_data['list'][0]['api_token'], '***')
        self.assertEqual(post_data['list'][0]['key'], '***')

    def test_no_staff_session_skips_logging(self):
        regular_user = User.objects.create_user('regular@example.com', 'password')
        regular_session = SessionStore()
        regular_session.create()

        request = self._get_request(data={'form_data': 'test'})
        request.user = regular_user
        request.session = regular_session

        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        self.assertEqual(StaffSessionAuditLog.objects.count(), 0)

    def test_impersonation_logging(self):
        impersonated_user = User.objects.create_user('user@example.com', 'password')

        request = self._get_request(path='/control/users/')
        request.user = impersonated_user

        # Simulate hijack session
        self.session['hijack_history'] = [self.user.pk]
        self.session['hijacker_session'] = self.session.session_key

        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.impersonating, impersonated_user)

    def test_query_parameter_masking(self):
        request = self._get_request(
            method='GET',
            path='/control/users/?search=keynote&password=abc&api_token=123&api_key=secret',
        )

        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)

        self.assertIn('search=keynote', log.url)
        self.assertIn('password=***', log.url)
        self.assertIn('api_token=***', log.url)
        self.assertIn('api_key=***', log.url)
        self.assertNotIn('abc', log.url)
        self.assertNotIn('123', log.url)
        self.assertNotIn('secret', log.url)

