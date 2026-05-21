from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0027_talkquestion_dependency_question_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='participation_mode',
            field=models.CharField(
                choices=[('virtual', 'Virtual (online)'), ('in_person', 'In-person')],
                default='in_person',
                help_text='Whether this ticket grants virtual (online) or in-person access.',
                max_length=50,
                verbose_name='Participation mode',
            ),
        ),
    ]
