from django.db import migrations, models
from django.db.models import Min


def flag_core_teams(apps, schema_editor):
    """
    Flag the Core Organizing Team of every organizer.

    Every organizer creation path creates the owner team in the same transaction as the organizer, with
    access to all events and the right to change teams and organizer settings. Its name is not reliable:
    it was "Administrators" before it became "Core Organizing Team", it is stored translated, and
    organizers can rename it. So the core team is the organizer's oldest team with that owner-level
    access.
    """
    Team = apps.get_model('base', 'Team')
    first_owner_teams = (
        Team.objects.filter(all_events=True, can_change_teams=True, can_change_organizer_settings=True)
        .values('organizer_id')
        .annotate(first_id=Min('id'))
        .values_list('first_id', flat=True)
    )
    Team.objects.filter(id__in=list(first_owner_teams)).update(is_core_team=True)


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0093_team_can_view_event_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='is_core_team',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Members of the core team are the owners of the organizer account and can perform '
                    'owner-only actions such as anonymizing event data. Only platform administrators can '
                    'change this.'
                ),
                verbose_name='Core Organizing Team',
            ),
        ),
        migrations.RunPython(flag_core_teams, migrations.RunPython.noop),
    ]
