from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0035_user_is_spam'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='has_interpretation',
            field=models.BooleanField(default=False, verbose_name='This session has live interpretation.'),
        ),
    ]
