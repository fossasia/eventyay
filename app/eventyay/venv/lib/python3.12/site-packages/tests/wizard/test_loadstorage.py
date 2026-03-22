from django.test import TestCase

from formtools.wizard.storage import MissingStorage, get_storage
from formtools.wizard.storage.base import BaseStorage


class TestLoadStorage(TestCase):
    def test_load_storage(self):
        self.assertIsInstance(
            get_storage('formtools.wizard.storage.base.BaseStorage', 'wizard1'),
            BaseStorage
        )

    def test_missing_storage(self):
        with self.assertRaises(MissingStorage):
            get_storage('formtools.wizard.storage.idontexist.IDontExistStorage', 'wizard1')
        with self.assertRaises(MissingStorage):
            get_storage('formtools.wizard.storage.base.IDontExistStorage', 'wizard1')
