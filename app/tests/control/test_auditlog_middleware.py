import json
from django.test import RequestFactory, TestCase
from django.contrib.sessions.backends.db import SessionStore

from eventyay.base.models.auth import User, StaffSession, StaffSessionAuditLog
from eventyay.control.middleware import AuditLogMiddleware


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
            session_key=self.session.session_key
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

    def test_post_data_masking_querydict(self):
        request = self._get_request(data={
            'normal_field': 'value',
            'password_1': 'secret123',
            'api_token': 'abc',
            'secret_key': 'def',
            'turnstile_SECRET': 'ghi',
            'csrfmiddlewaretoken': 'token123'
        })
        
        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)
        
        post_data = json.loads(log.post_data)
        self.assertEqual(post_data['normal_field'], ['value'])
        self.assertEqual(post_data['password_1'], ['***'])
        self.assertEqual(post_data['api_token'], ['***'])
        self.assertEqual(post_data['secret_key'], ['***'])
        self.assertEqual(post_data['turnstile_SECRET'], ['***'])
        self.assertEqual(post_data['csrfmiddlewaretoken'], ['***'])

    def test_post_data_masking_json(self):
        request = self._get_request(data={
            'nested': {
                'normal_field': 'value',
                'password_1': 'secret123',
            },
            'list': [
                {'api_token': 'abc'}
            ]
        }, content_type='application/json')
        
        middleware = AuditLogMiddleware(lambda req: None)
        middleware(request)

        log = self.staff_session.logs.first()
        self.assertIsNotNone(log)
        
        post_data = json.loads(log.post_data)
        self.assertEqual(post_data['nested']['normal_field'], 'value')
        self.assertEqual(post_data['nested']['password_1'], '***')
        self.assertEqual(post_data['list'][0]['api_token'], '***')

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
