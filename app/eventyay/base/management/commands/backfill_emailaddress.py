"""One-time management command to backfill allauth EmailAddress records.

THIS COMMAND IS ONE-TIME USE.
It should be run once on existing deployments after upgrading to the version
that introduces django-allauth social login, then deleted from the codebase.

Background
----------
Users created before django-allauth was integrated have no ``EmailAddress``
record in the ``account_emailaddress`` table.  When a user attempts to log in
via WikiMedia OAuth for the first time, allauth's ``_lookup_by_email()`` looks
up the user by matching ``SocialLogin.email_addresses`` against verified
``EmailAddress`` rows.  Without those rows, allauth considers the account new
and sends the user to the signup form, which then (correctly) detects the
duplicate email and sends an "Account Already Exists" notification.

This command creates a verified, primary ``EmailAddress`` row for every
``User`` whose email is not already tracked by allauth.  Filtering is done on
the ``(user_id, email)`` pair so that users who already have an
``EmailAddress`` for a *different* address still receive a row for their
current ``user.email``.

Usage
-----
Run once on each environment after deploying the allauth social-login feature::

    python manage.py backfill_emailaddress

Optional dry-run (prints what would be created without writing to the DB)::

    python manage.py backfill_emailaddress --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from allauth.account.models import EmailAddress

from eventyay.base.models import User


class Command(BaseCommand):
    help = (
        'ONE-TIME USE — backfill allauth EmailAddress records for pre-allauth users. '
        'Delete this command after it has been run on all environments.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print how many rows would be created without modifying the database.',
        )

    def handle(self, *args, dry_run: bool = False, **options):
        existing_for_user_email = EmailAddress.objects.filter(
            user_id=OuterRef('pk'),
            email=OuterRef('email'),
        )

        users_missing_email = (
            User.objects.filter(email__isnull=False)
            .exclude(email='')
            .annotate(has_email_address=Exists(existing_for_user_email))
            .filter(has_email_address=False)
        )

        count = users_missing_email.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry run: would create {count} EmailAddress record(s).'
                )
            )
            return

        # Users who already have a primary EmailAddress for another address must
        # not get a second primary — only set primary=True when none exists yet.
        existing_primary_user_ids = set(
            EmailAddress.objects.filter(primary=True).values_list('user_id', flat=True)
        )

        batch_size = 500
        created = 0
        batch = []
        for user in users_missing_email.iterator(chunk_size=batch_size):
            batch.append(EmailAddress(
                user=user,
                email=user.email,
                verified=True,
                primary=user.pk not in existing_primary_user_ids,
            ))
            if len(batch) >= batch_size:
                EmailAddress.objects.bulk_create(batch)
                created += len(batch)
                batch = []
        if batch:
            EmailAddress.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(
            self.style.SUCCESS(f'Created {created} EmailAddress record(s).')
        )
