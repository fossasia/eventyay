from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0006_always_enable_event_components'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='has_subevents',
            field=models.BooleanField(default=True, verbose_name='Event series'),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_video_creation',
            field=models.BooleanField(default=True, verbose_name='Add video call', help_text='Create Video platform for Event.'),
        ),
    ]
