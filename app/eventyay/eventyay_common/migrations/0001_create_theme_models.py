# Generated migration for theme models

from django.db import migrations, models
import django.db.models.deletion
import eventyay.eventyay_common.models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),  # Ensure base models exist first
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizerTheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                ('color_mode', models.CharField(choices=[('light', 'Light Mode'), ('dark', 'Dark Mode'), ('auto', 'Auto (System Preference)')], default='auto', help_text='Default color mode for this theme', max_length=10, verbose_name='Color Mode')),
                ('token_overrides', models.JSONField(blank=True, default=dict, help_text='JSON object containing token overrides (colors, typography, spacing, etc.)', validators=[eventyay.eventyay_common.models.validate_token_overrides], verbose_name='Design Token Overrides')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this theme is currently in use', verbose_name='Active')),
                ('description', models.TextField(blank=True, default='', help_text='Internal description of this theme', verbose_name='Description')),
                ('logo_url', models.URLField(blank=True, default='', help_text='URL to organization logo', verbose_name='Logo URL')),
                ('favicon_url', models.URLField(blank=True, default='', help_text='URL to organization favicon', verbose_name='Favicon URL')),
                ('organizer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='theme', to='base.organizer', verbose_name='Organizer')),
            ],
            options={
                'verbose_name': 'Organizer Theme',
                'verbose_name_plural': 'Organizer Themes',
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='EventTheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                ('color_mode', models.CharField(choices=[('light', 'Light Mode'), ('dark', 'Dark Mode'), ('auto', 'Auto (System Preference)')], default='auto', help_text='Default color mode for this theme', max_length=10, verbose_name='Color Mode')),
                ('token_overrides', models.JSONField(blank=True, default=dict, help_text='JSON object containing token overrides (colors, typography, spacing, etc.)', validators=[eventyay.eventyay_common.models.validate_token_overrides], verbose_name='Design Token Overrides')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this theme is currently in use', verbose_name='Active')),
                ('description', models.TextField(blank=True, default='', help_text='Internal description of this theme', verbose_name='Description')),
                ('inherit_organizer_theme', models.BooleanField(default=True, help_text='Whether to inherit token overrides from the organizer theme', verbose_name='Inherit Organizer Theme')),
                ('custom_css', models.TextField(blank=True, default='', help_text='Additional custom CSS rules for this event', verbose_name='Custom CSS')),
                ('event', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='theme', to='base.event', verbose_name='Event')),
            ],
            options={
                'verbose_name': 'Event Theme',
                'verbose_name_plural': 'Event Themes',
                'ordering': ['-created'],
            },
        ),
    ]
