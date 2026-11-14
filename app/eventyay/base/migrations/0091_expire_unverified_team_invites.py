"""Require reissue of invitations created before delegation was checked."""

from django.db import migrations


def expire_unverified_team_invites(apps, schema_editor):
    TeamInvite = apps.get_model('base', 'TeamInvite')
    TeamInvite.objects.using(schema_editor.connection.alias).filter(state='pending').update(state='expired')


class Migration(migrations.Migration):
    dependencies = [('base', '0090_team_invite_state')]

    operations = [migrations.RunPython(expire_unverified_team_invites, migrations.RunPython.noop)]
