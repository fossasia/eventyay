# Generated manually for speaker vouchers (#7037)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0089_organizer_request'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpeakerVoucherSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                (
                    'enabled',
                    models.BooleanField(
                        default=False,
                        help_text='Allow sending ticket vouchers to speakers with confirmed sessions.',
                        verbose_name='Enable speaker vouchers',
                    ),
                ),
                (
                    'voucher_tag',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='The tag that identifies the voucher batch in Tickets → Vouchers.',
                        max_length=255,
                        verbose_name='Voucher batch (tag)',
                    ),
                ),
                (
                    'event',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='speaker_voucher_settings',
                        to='base.event',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Speaker voucher settings',
                'verbose_name_plural': 'Speaker voucher settings',
            },
        ),
        migrations.CreateModel(
            name='SpeakerVoucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('not_sent', 'Not sent'),
                            ('sent', 'Sent — not claimed'),
                            ('claimed', 'Claimed'),
                        ],
                        default='not_sent',
                        max_length=20,
                        verbose_name='Voucher status',
                    ),
                ),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Sent at')),
                (
                    'event',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='speaker_vouchers',
                        to='base.event',
                    ),
                ),
                (
                    'speaker_profile',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='voucher_assignment',
                        to='base.speakerprofile',
                    ),
                ),
                (
                    'voucher',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='speaker_voucher_link',
                        to='base.voucher',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Speaker voucher',
                'verbose_name_plural': 'Speaker vouchers',
            },
        ),
        migrations.AlterField(
            model_name='mailtemplate',
            name='role',
            field=models.CharField(
                choices=[
                    ('submission.new', 'Acknowledge proposal submission'),
                    ('submission.new.internal', 'New proposal (organiser notification)'),
                    ('submission.state.accepted', 'Proposal accepted'),
                    ('submission.state.rejected', 'Proposal rejected'),
                    ('speaker.invite', 'Add a speaker to a proposal (new account)'),
                    ('speaker.invite.existing', 'Add a speaker to a proposal (existing account)'),
                    ('question.reminder', 'Custom fields reminder'),
                    ('schedule.new', 'New schedule published'),
                    ('speaker.voucher', 'Speaker voucher'),
                ],
                default=None,
                editable=False,
                max_length=30,
                null=True,
            ),
        ),
    ]
