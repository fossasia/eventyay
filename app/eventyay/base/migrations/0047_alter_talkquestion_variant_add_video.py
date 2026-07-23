# Generated manually for TalkQuestionVariant.VIDEO

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0046_user_show_publicly_default_false'),
    ]

    operations = [
        migrations.AlterField(
            model_name='talkquestion',
            name='variant',
            field=models.CharField(
                choices=[
                    ('number', 'Number'),
                    ('string', 'Text (one-line)'),
                    ('text', 'Multi-line text'),
                    ('url', 'URL'),
                    ('video', 'Video link'),
                    ('date', 'Date'),
                    ('datetime', 'Date and time'),
                    ('boolean', 'Confirmation'),
                    ('file', 'File upload'),
                    ('choices', 'Radio button (Choose one option)'),
                    ('multiple_choice', 'Checkbox (Choose one or several options)'),
                    ('select', 'Select (one option)'),
                    ('country', 'Country List'),
                ],
                default='string',
                max_length=15,
            ),
        ),
    ]
