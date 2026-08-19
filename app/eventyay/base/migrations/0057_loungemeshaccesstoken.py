from django.db import migrations, models
import django.db.models.deletion
import eventyay.base.models.loungemesh
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0056_global_plugin_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoungeMeshAccessToken',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'token',
                    models.CharField(
                        default=eventyay.base.models.loungemesh.generate_opaque_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ('is_moderator', models.BooleanField(default=False)),
                ('display_name', models.CharField(blank=True, max_length=300)),
                ('order_code', models.CharField(blank=True, max_length=64)),
                ('expires', models.DateTimeField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                (
                    'event',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='loungemesh_tokens',
                        to='base.event',
                    ),
                ),
                (
                    'room',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='loungemesh_tokens',
                        to='base.room',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='loungemesh_tokens',
                        to='base.user',
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='loungemeshaccesstoken',
            index=models.Index(fields=['token'], name='base_lounge_token_idx'),
        ),
        migrations.AddIndex(
            model_name='loungemeshaccesstoken',
            index=models.Index(fields=['expires'], name='base_lounge_expires_idx'),
        ),
    ]
