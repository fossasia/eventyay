from django.core.management.commands.compilemessages import Command as CompilemessagesCommand

from eventyay.common.locale_extract import COMPILE_IGNORE_PATTERNS, merge_ignore_patterns


class Command(CompilemessagesCommand):
    help = 'Compile project gettext catalogs, skipping .venv and vendor trees.'

    def handle(self, **options):
        options['ignore_patterns'] = merge_ignore_patterns(
            options.get('ignore_patterns'), COMPILE_IGNORE_PATTERNS
        )
        return super().handle(**options)
