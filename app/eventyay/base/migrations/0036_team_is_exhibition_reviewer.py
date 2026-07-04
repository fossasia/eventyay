from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0035_user_is_spam'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='is_exhibition_reviewer',
            field=models.BooleanField(default=False, help_text='Can screen and evaluate exhibitor and sponsor proposals but cannot edit event setup, manage exhibitors, or change other settings.', verbose_name='Exhibitor Reviewer — can only review exhibitor proposals'),
        ),
    ]
