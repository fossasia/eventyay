from django.db import migrations, models


def grant_bank_transfer_to_order_editors(apps, schema_editor):
    Team = apps.get_model('base', 'Team')
    Team.objects.filter(can_change_orders=True).update(can_manage_bank_transfers=True)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0041_make_event_email_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='can_manage_bank_transfers',
            field=models.BooleanField(
                default=False,
                help_text='Import bank data and export refunds for bank transfer payments.',
                verbose_name='Can manage bank transfers',
            ),
        ),
        migrations.RunPython(grant_bank_transfer_to_order_editors, migrations.RunPython.noop),
    ]
