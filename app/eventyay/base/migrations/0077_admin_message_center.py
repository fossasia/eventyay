import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0076_default_speaker_questions'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminEmailQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_group', models.CharField(
                    choices=[
                        ('all_users', 'All registered users'),
                        ('all_organisers', 'All organisers'),
                        ('event_organisers', 'Organisers of selected events'),
                        ('event_team_members', 'Event team members'),
                        ('speakers', 'Speakers'),
                        ('reviewers', 'Reviewers'),
                        ('attendees', 'Attendees'),
                        ('selected_users', 'Selected users'),
                    ],
                    default='all_users',
                    max_length=30,
                    verbose_name='Recipient group',
                )),
                ('subject', models.CharField(blank=True, default='', max_length=500, verbose_name='Subject')),
                ('message', models.TextField(blank=True, default='', verbose_name='Message')),
                ('reply_to', models.CharField(blank=True, default='', max_length=254, verbose_name='Reply-To')),
                ('bcc', models.TextField(blank=True, default='', verbose_name='BCC')),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('queued', 'Queued'),
                        ('sending', 'Sending'),
                        ('sent', 'Sent'),
                        ('cancelled', 'Cancelled'),
                    ],
                    db_index=True,
                    default='draft',
                    max_length=20,
                    verbose_name='Status',
                )),
                ('scheduled_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Scheduled for')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Sent at')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attachment', models.UUIDField(blank=True, null=True, verbose_name='Attachment')),
                ('recipient_count_snapshot', models.PositiveIntegerField(default=0, verbose_name='Recipient count at save time')),
            ],
            options={
                'verbose_name': 'Admin email',
                'verbose_name_plural': 'Admin emails',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AdminEmailQueueFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_status', models.CharField(blank=True, default='', max_length=20, verbose_name='Account status')),
                ('user_role', models.CharField(blank=True, default='', max_length=20, verbose_name='User role')),
                ('language', models.CharField(blank=True, default='', max_length=20, verbose_name='Language / locale')),
                ('created_after', models.DateTimeField(blank=True, null=True)),
                ('created_before', models.DateTimeField(blank=True, null=True)),
                ('last_active_after', models.DateTimeField(blank=True, null=True)),
                ('last_active_before', models.DateTimeField(blank=True, null=True)),
                ('event_status', models.CharField(blank=True, default='', max_length=20)),
                ('event_date_from', models.DateField(blank=True, null=True)),
                ('event_date_to', models.DateField(blank=True, null=True)),
                ('event_ids', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), blank=True, default=list, size=None)),
                ('organiser_ids', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), blank=True, default=list, size=None)),
                ('selected_user_ids', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), blank=True, default=list, size=None)),
                ('organiser_status', models.CharField(blank=True, default='', max_length=30)),
                ('billing_status', models.CharField(blank=True, default='', max_length=30)),
                ('ticketing_status', models.CharField(blank=True, default='', max_length=30)),
                ('cfp_status', models.CharField(blank=True, default='', max_length=30)),
                ('setup_status', models.CharField(blank=True, default='', max_length=30)),
                ('exclude_admins', models.BooleanField(default=False, verbose_name='Exclude platform admins')),
                ('exclude_inactive', models.BooleanField(default=False, verbose_name='Exclude inactive users')),
                ('exclude_unconfirmed_email', models.BooleanField(default=False, verbose_name='Exclude users without confirmed email')),
            ],
            options={
                'verbose_name': 'Admin email filter',
            },
        ),
        migrations.CreateModel(
            name='AdminEmailQueueRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('reason', models.CharField(blank=True, default='', max_length=255, verbose_name='Reason included')),
                ('sent', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['email'],
            },
        ),
        migrations.AddField(
            model_name='adminemailqueue',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_email_queue', to=settings.AUTH_USER_MODEL, verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='adminemailqueuefilter',
            name='mail',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='filters', to='base.adminemailqueue'),
        ),
        migrations.AddField(
            model_name='adminemailqueuerecipient',
            name='mail',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='base.adminemailqueue'),
        ),
        migrations.AddField(
            model_name='adminemailqueuerecipient',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='adminemailqueuerecipient',
            unique_together={('mail', 'email')},
        ),
    ]
