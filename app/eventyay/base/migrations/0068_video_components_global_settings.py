from django.db import migrations, models


def initialize_global_video_settings(apps, schema_editor):
    SettingsStore = apps.get_model('base', 'GlobalSettingsObject_SettingsStore')

    video_settings = [
        'video_jitsi_enabled',
        'video_bbb_enabled',
        'video_janus_enabled',
        'video_streaming_enabled',
        'video_chat_channels_enabled',
        'video_qna_enabled',
        'video_polls_enabled',
    ]

    for key in video_settings:
        if not SettingsStore.objects.filter(key=key).exists():
            SettingsStore.objects.create(key=key, value='True')


def reverse_global_video_settings(apps, schema_editor):
    SettingsStore = apps.get_model('base', 'GlobalSettingsObject_SettingsStore')

    video_settings = [
        'video_jitsi_enabled',
        'video_bbb_enabled',
        'video_janus_enabled',
        'video_streaming_enabled',
        'video_chat_channels_enabled',
        'video_qna_enabled',
        'video_polls_enabled',
    ]

    SettingsStore.objects.filter(key__in=video_settings).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0067_user_profile_picture_user_profile_picture_thumbnail_and_more'),
    ]

    operations = [
        migrations.RunPython(initialize_global_video_settings, reverse_global_video_settings),
        migrations.RenameIndex(
            model_name='gmailoauthcredential',
            new_name='base_gmailo_event_i_133776_idx',
            old_name='base_gmailo_event_i_6f0d0d_idx',
        ),
        migrations.RenameIndex(
            model_name='gmailoauthcredential',
            new_name='base_gmailo_is_acti_22cf9d_idx',
            old_name='base_gmailo_is_acti_0d8f8f_idx',
        ),
        migrations.RemoveField(
            model_name='bbbserver',
            name='event_exclusive',
        ),
        migrations.RemoveField(
            model_name='janusserver',
            name='event_exclusive',
        ),
        migrations.RemoveField(
            model_name='jitsiserver',
            name='event_exclusive',
        ),
        migrations.RemoveField(
            model_name='turnserver',
            name='event_exclusive',
        ),
        migrations.AddField(
            model_name='bbbserver',
            name='events_exclusive',
            field=models.ManyToManyField(blank=True, to='base.event'),
        ),
        migrations.AddField(
            model_name='janusserver',
            name='events_exclusive',
            field=models.ManyToManyField(blank=True, to='base.event'),
        ),
        migrations.AddField(
            model_name='jitsiserver',
            name='events_exclusive',
            field=models.ManyToManyField(blank=True, to='base.event'),
        ),
        migrations.AddField(
            model_name='turnserver',
            name='events_exclusive',
            field=models.ManyToManyField(blank=True, to='base.event'),
        ),
        migrations.AlterField(
            model_name='streamschedule',
            name='stream_type',
            field=models.CharField(choices=[('youtube', 'YouTube'), ('vimeo', 'Vimeo'), ('hls', 'HLS')], default='youtube', max_length=50, verbose_name='Stream Type'),
        ),
        migrations.AlterField(
            model_name='team',
            name='can_video_manage_content',
            field=models.BooleanField(default=False, help_text='Create and edit stages and chat/video channels; edit and delete rooms.', verbose_name='Video: Can manage rooms and content'),
        ),
    ]
