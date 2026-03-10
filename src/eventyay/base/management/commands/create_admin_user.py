from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from getpass import getpass

from eventyay.base.models.auth import User


class Command(BaseCommand):
    help = 'Creates an admin user without setting is_superuser to True.'

    def handle(self, *args, **options):
        email = self.get_email()
        password = self.get_password()

        # Prevent duplicate users
        if User.objects.filter(email=email).exists():
            raise CommandError(f"A user with email {email} already exists.")

        # Create admin user
        user = User.objects.create_adminuser(email=email, password=password)

        self.stdout.write(self.style.SUCCESS(f"Successfully created admin user: {user.email}"))

    def get_email(self):
        """Prompt for email and validate format."""
        while True:
            email = input("E-mail: ").strip()
            if not email:
                self.stderr.write(self.style.ERROR("The email field cannot be empty."))
                continue
            try:
                validate_email(email)
                return email
            except ValidationError:
                self.stderr.write(self.style.ERROR("Please enter a valid email address."))

    def get_password(self):
        """Prompt for password and apply Django's password validation."""
        while True:
            password1 = self._get_password("Password: ")
            password2 = self._get_password("Confirm password: ")

            if password1 != password2:
                self.stderr.write(self.style.ERROR("Passwords do not match. Please try again."))
                continue

            try:
                validate_password(password1)
                return password1
            except ValidationError as e:
                for error in e.messages:
                    self.stderr.write(self.style.ERROR(error))

    def _get_password(self, prompt):
        """Securely read a password input."""
        return getpass(prompt)
