import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0063_jitsi_video_moderator_permissions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GmailOAuthCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_email', models.EmailField(max_length=254, verbose_name='Sender email')),
                ('encrypted_refresh_token', models.TextField()),
                ('encrypted_access_token', models.TextField(blank=True, default='')),
                ('token_expiry', models.DateTimeField(blank=True, null=True)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('daily_send_count', models.PositiveIntegerField(default=0)),
                ('daily_send_count_date', models.DateField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                (
                    'connected_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='gmail_credentials',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'event',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='gmail_credentials',
                        to='base.event',
                        verbose_name='Event',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Gmail OAuth credential',
                'verbose_name_plural': 'Gmail OAuth credentials',
                'indexes': [
                    models.Index(fields=['event', 'is_active'], name='base_gmailo_event_i_6f0d0d_idx'),
                    models.Index(fields=['is_active'], name='base_gmailo_is_acti_0d8f8f_idx'),
                ],
            },
        ),
    ]
