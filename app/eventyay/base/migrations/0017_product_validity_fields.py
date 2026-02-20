from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0016_alter_talkquestion_variant'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='validity_mode',
            field=models.CharField(
                blank=True,
                choices=[('', 'Use event start/end (default)'), ('fixed', 'Fixed date/time range')],
                default='',
                help_text=(
                    'Determines when the purchased ticket is valid for entry. '
                    'By default, the ticket is valid for the entire event duration. '
                    'Use a fixed range to restrict validity to specific dates, e.g. '
                    'for day tickets in multi-day events.'
                ),
                max_length=10,
                verbose_name='Ticket validity',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='validity_fixed_from',
            field=models.DateTimeField(
                blank=True,
                help_text='The ticket is valid for entry starting at this date and time.',
                null=True,
                verbose_name='Valid from',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='validity_fixed_until',
            field=models.DateTimeField(
                blank=True,
                help_text='The ticket is valid for entry until this date and time.',
                null=True,
                verbose_name='Valid until',
            ),
        ),
    ]
