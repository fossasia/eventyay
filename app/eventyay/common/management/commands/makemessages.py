from django.core.management.commands.makemessages import Command as MakemessagesCommand

from eventyay.common.locale_extract import apply_makemessages_defaults


class Command(MakemessagesCommand):
    help = (
        'Extract gettext catalogs, skipping node_modules/dist/build and the English '
        'source language. Vue apps still need npm run i18n:extract.'
    )

    def handle(self, *args, **options):
        apply_makemessages_defaults(options)
        return super().handle(*args, **options)
