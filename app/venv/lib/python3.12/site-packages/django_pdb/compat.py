# -*- coding: utf-8 -*-

import os

from django.core.management import find_commands

try:
    from django_pdb.apps import DjangoPdbConfig
    from django.apps import apps
except ImportError as e:
    # So django < 1.7
    from django.core.management import find_management_module
    import django_pdb.management

    def load_management_modules(commands):
        # Find the installed apps
        try:
            from django.conf import settings
            _apps = settings.INSTALLED_APPS
        except (AttributeError, EnvironmentError, ImportError):
            _apps = []

        # Find and load the management module for each installed app above
        # this one.
        for app_name in _apps:
            try:
                path = find_management_module(app_name)
                if path == django_pdb.management.__path__[0]:
                    # Found this app
                    break

                commands.update(
                    dict([(name, app_name) for name in find_commands(path)])
                )
            except ImportError:
                pass  # No management module - ignore this app
else:
    def load_management_modules(commands):
        app_configs = [app_config for app_config in apps.get_app_configs() if app_config.name != DjangoPdbConfig.name]
        for app_config in reversed(app_configs):
            path = os.path.join(app_config.path, 'management')
            commands.update({name: app_config.name for name in find_commands(path)})
