"""Management command to rename existing 'Administrators' teams to 'Core Organizing Team'"""

from django.core.management.base import BaseCommand
from django.db import transaction

from eventyay.base.models import Team


class Command(BaseCommand):
    help = 'Rename existing "Administrators" teams to "Core Organizing Team"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find all teams named "Administrators"
        admin_teams = Team.objects.filter(name='Administrators')
        admin_teams_count = admin_teams.count()
        
        if admin_teams_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nNo teams named "Administrators" found. All teams are already updated!'
                )
            )
            return
        
        self.stdout.write(f'\nFound {admin_teams_count} team(s) named "Administrators":\n')
        self.stdout.write('=' * 80)
        
        for team in admin_teams:
            organizer_name = team.organizer.name if team.organizer else 'N/A'
            organizer_slug = team.organizer.slug if team.organizer else 'N/A'
            member_count = team.members.count()
            
            self.stdout.write(
                f'\nTeam ID: {team.id}\n'
                f'  Organizer: {organizer_name} ({organizer_slug})\n'
                f'  Members: {member_count}\n'
                f'  Current Name: "{team.name}"\n'
                f'  New Name: "Core Organizing Team"'
            )
        
        self.stdout.write('\n' + '=' * 80)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n DRY RUN: {admin_teams_count} team(s) would be renamed.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Run without --dry-run to apply changes.'
                )
            )
        else:
            # Update all teams
            updated_count = admin_teams.update(name='Core Organizing Team')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully renamed {updated_count} team(s) from '
                    f'"Administrators" to "Core Organizing Team"'
                )
            )
            
            # Log the action for each team
            for team in Team.objects.filter(name='Core Organizing Team'):
                team.log_action(
                    'eventyay.team.changed',
                    data={
                        'name': 'Core Organizing Team',
                        '_old_name': 'Administrators',
                        '_migration': True,
                    }
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    'All changes have been logged.'
                )
            )
