from django.test import TestCase

from formtools.wizard.storage.base import BaseStorage


class TestBaseStorage(TestCase):

    def test_subclass_can_override_get_current_step(self):
        class MyStorage(BaseStorage):
            def _get_current_step(self):
                return 'foo'

        self.assertEqual(MyStorage('/').current_step, 'foo')

    def test_subclass_can_override_get_extra_data(self):
        class MyStorage(BaseStorage):
            def _get_extra_data(self):
                return 'foo'

        self.assertEqual(MyStorage('/').extra_data, 'foo')
