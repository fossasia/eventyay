from django.core.management.base import BaseCommand
from django.core.management import CommandError
from getpass import getpass

from eventyay.base.models.auth import User

class Command(BaseCommand):
    help = 'Creates an admin user without setting is_superuser to True.'

    def add_arguments(self, parser):
        # Optional argument for full name
        parser.add_argument('--fullname', type=str, help='Full name of the admin user.')

    def handle(self, *args, **options):
        email = self.get_email()
        password = self.get_password()
        fullname = options.get('fullname') or self.get_fullname()
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise CommandError(f"A user with email {email} already exists.")
        
        # Create the admin user using the custom UserManager
        user = User.objects.create_adminuser(
            email=email,
            password=password,
            fullname=fullname
        )
        
        self.stdout.write(self.style.SUCCESS(f"Successfully created admin user: {user.email}"))

    def get_email(self):
        """
        Prompt for email if not provided in command-line arguments.
        """
        while True:
            if email := input("E-mail: ").strip():
                return email
            self.stderr.write(self.style.ERROR("The email field cannot be empty."))

    def get_password(self):
        """
        Prompt for a password securely.
        """
        while True:
            password1 = self._get_password("Password: ")
            password2 = self._get_password("Confirm password: ")

            if password1 != password2:
                self.stderr.write(self.style.ERROR("Passwords do not match. Please try again."))
                continue

            if len(password1) < 8:  # Optional: You can validate password strength
                self.stderr.write(self.style.ERROR("Password must be at least 8 characters long."))
                continue

            return password1

    def get_fullname(self):
        """
        Prompt for full name if not provided via options.
        Returns None if no name is entered.
        """
        fullname = input("Full name (Optional): ").strip()
        
        return fullname if fullname else None

    def _get_password(self, prompt):
        """
        Helper to handle secure password input.
        """
        return getpass(prompt)
