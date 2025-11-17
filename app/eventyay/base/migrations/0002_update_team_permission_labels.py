# Generated migration for updating Team permission labels and help text

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='team',
            name='can_change_submissions',
            field=models.BooleanField(
                default=False,
                help_text='Can edit submission details, change proposal states (accept/reject/waitlist), manage submission metadata, and oversee the review workflow. This provides full management permissions beyond standard reviewing.',
                verbose_name='Can edit and manage submissions'
            ),
        ),
        migrations.AlterField(
            model_name='team',
            name='is_reviewer',
            field=models.BooleanField(
                default=False,
                help_text='Can review and provide feedback on submissions but cannot edit details or change submission states.',
                verbose_name='Reviewer'
            ),
        ),
    ]
