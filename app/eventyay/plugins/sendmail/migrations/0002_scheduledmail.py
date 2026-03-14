# Generated migration for ScheduledMail and ScheduledMailLog models

import django.contrib.postgres.fields
import django.db.models.deletion
import i18nfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sendmail', '0001_initial'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledMail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True)),
                ('subject', i18nfield.fields.I18nTextField(blank=True, null=True)),
                ('message', i18nfield.fields.I18nTextField(blank=True, null=True)),
                ('recipients', models.CharField(
                    choices=[('orders', 'Orders'), ('attendees', 'Attendees'), ('both', 'Both')],
                    default='orders',
                    max_length=10,
                )),
                ('order_status', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=20), blank=True, default=list, size=None,
                )),
                ('products', django.contrib.postgres.fields.ArrayField(
                    base_field=models.BigIntegerField(), blank=True, default=list, size=None,
                )),
                ('checkin_lists', django.contrib.postgres.fields.ArrayField(
                    base_field=models.IntegerField(), blank=True, default=list, size=None,
                )),
                ('has_filter_checkins', models.BooleanField(default=False)),
                ('not_checked_in', models.BooleanField(default=False)),
                ('subevent', models.IntegerField(blank=True, null=True)),
                ('schedule_type', models.CharField(
                    choices=[
                        ('absolute', 'Absolute'),
                        ('relative_before_event_start', 'Relative, before event start'),
                        ('relative_before_event_end', 'Relative, before event end'),
                        ('relative_after_event_start', 'Relative, after event start'),
                        ('relative_after_event_end', 'Relative, after event end'),
                    ],
                    default='absolute',
                    max_length=40,
                )),
                ('send_date', models.DateTimeField(blank=True, null=True)),
                ('send_offset_days', models.IntegerField(blank=True, null=True)),
                ('send_offset_time', models.TimeField(blank=True, null=True)),
                ('last_execution', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scheduled_mails',
                    to='base.event',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ScheduledMailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fired_at', models.DateTimeField(auto_now_add=True)),
                ('recipient_count', models.IntegerField(default=0)),
                ('error', models.TextField(blank=True, null=True)),
                ('rule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs',
                    to='sendmail.scheduledmail',
                )),
            ],
            options={
                'ordering': ['-fired_at'],
            },
        ),
    ]
