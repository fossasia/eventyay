# Generated migration for featured speakers feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_team_can_video_create_channels_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='speakerprofile',
            name='is_featured',
            field=models.BooleanField(
                default=False,
                help_text='Featured speakers will be displayed on the event landing page',
                verbose_name='Featured speaker'
            ),
        ),
        migrations.AddField(
            model_name='speakerprofile',
            name='order',
            field=models.IntegerField(
                default=0,
                help_text='Order in which speakers are displayed (lower numbers appear first)',
                verbose_name='Display order'
            ),
        ),
        migrations.AddIndex(
            model_name='speakerprofile',
            index=models.Index(
                fields=['event', 'is_featured', 'order'],
                name='speaker_featured_order_idx'
            ),
        ),
    ]
