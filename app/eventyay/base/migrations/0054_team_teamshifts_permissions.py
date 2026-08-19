from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0053_jitsiserver'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='teamshifts_role',
            field=models.CharField(
                blank=True,
                choices=[('coordinator', 'Event Coordinator'), ('lead', 'Team Lead')],
                default='',
                max_length=20,
                verbose_name='TeamShifts role',
            ),
        ),
        migrations.AddField(
            model_name='team',
            name='all_teamshifts_roles',
            field=models.BooleanField(default=False, verbose_name='All teamshifts roles'),
        ),
        migrations.AddField(
            model_name='team',
            name='limit_teamshifts_roles',
            field=models.JSONField(blank=True, default=list, verbose_name='Limit teamshifts roles'),
        ),
        migrations.AddField(
            model_name='team',
            name='hide_teamshifts_emails',
            field=models.BooleanField(default=False, verbose_name='Hide email addresses'),
        ),
    ]
