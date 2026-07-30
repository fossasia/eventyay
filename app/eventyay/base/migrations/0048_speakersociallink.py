import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0047_team_can_manage_social_media'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpeakerSocialLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'network',
                    models.CharField(
                        choices=[
                            ('website', 'Website'),
                            ('facebook', 'Facebook'),
                            ('flickr', 'Flickr'),
                            ('github', 'GitHub'),
                            ('gitlab', 'GitLab'),
                            ('gitter', 'Gitter'),
                            ('google_groups', 'Google Groups'),
                            ('instagram', 'Instagram'),
                            ('linkedin', 'LinkedIn'),
                            ('mastodon', 'Mastodon'),
                            ('patreon', 'Patreon'),
                            ('telegram', 'Telegram'),
                            ('vimeo', 'Vimeo'),
                            ('vk', 'VK'),
                            ('weibo', 'Weibo'),
                            ('x', 'X'),
                            ('xing', 'Xing'),
                            ('youtube', 'YouTube'),
                        ],
                        max_length=32,
                    ),
                ),
                ('url', models.URLField(verbose_name='URL')),
                (
                    'profile',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='social_links',
                        to='base.speakerprofile',
                    ),
                ),
            ],
            options={
                'ordering': ('network', 'url'),
            },
        ),
    ]
