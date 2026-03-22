from django.test import TestCase

from formtools.wizard.storage.session import SessionStorage

from .storage import TestStorage


class TestSessionStorage(TestStorage, TestCase):
    def get_storage(self):
        return SessionStorage
