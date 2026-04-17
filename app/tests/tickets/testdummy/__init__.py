from django.apps import AppConfig


class TestDummyApp(AppConfig):
    name = 'tests.tickets.testdummy'
    verbose_name = '.testdummy'

    class PretixPluginMeta:
        name = '.testdummy'
        version = '1.0.0'

    def ready(self):
        from tests.tickets.testdummy import signals  # noqa


default_app_config = 'tests.tickets.testdummy.TestDummyApp'
