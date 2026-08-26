from django.core.management.commands.compilemessages import Command as CompilemessagesCommand

from eventyay.common.locale_extract import merge_ignore_patterns


class Command(CompilemessagesCommand):
    help = 'Compile gettext catalogs, skipping node_modules/dist/build.'

    def handle(self, **options):
        options['ignore_patterns'] = merge_ignore_patterns(options.get('ignore_patterns'))
        return super().handle(**options)
