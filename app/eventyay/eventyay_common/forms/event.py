import logging
import os
from urllib.parse import urlparse

from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from eventyay.base.forms import I18nModelForm, SettingsForm
from eventyay.base.models import Event
from eventyay.base.settings import validate_event_settings
from eventyay.common.language import get_language_choices_native_with_ui_name
from eventyay.common.urls import get_file_url_path, is_http_url
from eventyay.control.forms import SlugWidget, SplitDateTimeField, SplitDateTimePickerWidget
from eventyay.helpers.image_optimize import optimize_uploaded_image
from eventyay.multidomain.models import KnownDomain
from eventyay.orga.forms.widgets import MultipleLanguagesWidget

logger = logging.getLogger(__name__)


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )

    auto_fields = [
        'locales',
        'locale',
        'region',
        'imprint_url',
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'logo_show_title',
        'og_image',
        'primary_color',
        'header_background_color',
        'header_text_color',
        'navigation_text_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'frontpage_text',
        'menu_label_tickets',
        'menu_label_join_video',
    ]

    def clean(self):
        data = super().clean()
        settings_dict = self.get_initial_settings()
        settings_dict.update(data)
        validate_event_settings(self.event, settings_dict)
        return data

    def save(self):
        for image_field in ('event_logo_image', 'logo_image'):
            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            new_value = self.cleaned_data.get(image_field)
            if is_http_url(current_value) and (isinstance(new_value, UploadedFile) or not new_value):
                del self.event.settings[image_field]
            current_file = get_file_url_path(current_value)
            if isinstance(new_value, str) and current_file and current_value != new_value:
                default_storage.delete(current_file)

                base_path, _ = os.path.splitext(current_file)
                orig_ext = self.event.settings.get(f'{image_field}_original_ext', as_type=str)
                if orig_ext:
                    default_storage.delete(f'{base_path}_original.{orig_ext}')

            if isinstance(new_value, UploadedFile):
                self.cleaned_data[image_field] = self._save_optimized(new_value, image_field)

        return super().save()

    def _save_optimized(self, uploaded: UploadedFile, setting_key: str) -> str | UploadedFile:
        """
        Resize and re-encode *uploaded*, persist the original alongside it,
        and return the path to the optimized file so that the settings form
        stores the optimized variant.
        """
        try:
            result = optimize_uploaded_image(uploaded, setting_key)
        except (OSError, ValueError):
            logger.exception(
                'Image optimization failed for %s; storing original unmodified',
                setting_key,
            )
            uploaded.seek(0)
            return uploaded

        new_filename = self.get_new_filename(uploaded.name or setting_key)
        base_path, _ = os.path.splitext(new_filename)

        # Persist the optimized file.
        optimized_name = f'{base_path}.{result.optimized_ext}'
        try:
            optimized_path = default_storage.save(optimized_name, result.optimized)
            logger.info('Stored optimized image at %s', optimized_path)
        except OSError:
            logger.exception('Could not store optimized image for %s', setting_key)
            return uploaded

        # Persist the original file alongside it.
        original_name = f'{base_path}_original.{result.original_ext}'
        try:
            original_path = default_storage.save(original_name, result.original)
            logger.info('Stored original image at %s', original_path)
            # Store the original extension so PR2 can easily find it later
            self.event.settings.set(f'{setting_key}_original_ext', result.original_ext)
        except OSError:
            logger.exception('Could not store original image for %s', setting_key)

        # Return a string so Hierarkey stores this path directly instead of wrapping it again
        return f"file://{optimized_path}"

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)
        localized_language_choices = get_language_choices_native_with_ui_name()
        for fname in ('locales', 'content_locales'):
            if fname in self.fields:
                self.fields[fname].choices = localized_language_choices
        # Ensure the language selectors use the custom dropdown widget even if defaults are not picked up elsewhere,
        # while preserving any existing widget attributes (ids, data-*, classes).
        for fname in ('locales', 'content_locales'):
            if fname in self.fields:
                old_widget = self.fields[fname].widget
                self.fields[fname].widget = MultipleLanguagesWidget(
                    choices=self.fields[fname].choices, attrs=getattr(old_widget, 'attrs', None)
                )
        if self.event and 'content_locales' in self.fields:
            self.fields['content_locales'].initial = self.event.content_locales


class EventUpdateForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        self.change_slug = kwargs.pop('change_slug', False)
        self.domain_field_enabled = kwargs.pop('domain', False)

        kwargs.setdefault('initial', {})
        self.instance = kwargs['instance']
        if self.domain_field_enabled and self.instance:
            initial_domain = self.instance.domains.first()
            if initial_domain:
                kwargs['initial'].setdefault('domain', initial_domain.domainname)

        super().__init__(*args, **kwargs)
        if self.instance and self.instance.organizer:
            self.fields['slug'].widget.organizer = self.instance.organizer
            self.fields['slug'].widget.event = self.instance

        if not self.change_slug:
            self.fields['slug'].widget.attrs['readonly'] = 'readonly'
        self.fields['location'].widget.attrs['rows'] = '3'
        self.fields['location'].widget.attrs['placeholder'] = _('Sample Conference Center\nHeidelberg, Germany')

        # Configure email field with canonical label and help text
        self.fields['email'].required = True
        self.fields['email'].label = _('Organizer email address')
        self.fields['email'].help_text = _("We'll show this publicly to allow attendees to contact you.")

        if self.domain_field_enabled:
            self.fields['domain'] = forms.CharField(
                max_length=255,
                label=_('Custom domain'),
                required=False,
                help_text=_('You need to configure the custom domain in the webserver beforehand.'),
            )

    def clean_domain(self):
        if not self.domain_field_enabled:
            return None
        d = self.cleaned_data.get('domain')
        if d:
            if d == urlparse(django_settings.SITE_URL).hostname:
                raise ValidationError(_('You cannot choose the base domain of this installation.'))
            if KnownDomain.objects.filter(domainname=d).exclude(event=self.instance.pk).exists():
                raise ValidationError(_('This domain is already in use for a different event or organizer.'))
        return d

    def save(self, commit=True):
        instance = super().save(commit)
        if self.domain_field_enabled and 'domain' in self.cleaned_data:
            current_domain = instance.domains.first()
            domain_value = self.cleaned_data['domain']
            if domain_value:
                if current_domain and current_domain.domainname != domain_value:
                    current_domain.delete()
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
                elif not current_domain:
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
            elif current_domain:
                current_domain.delete()
            instance.cache.clear()
        return instance

    def clean_slug(self):
        if self.change_slug:
            return self.cleaned_data['slug']
        return self.instance.slug

    class Meta:
        model = Event
        fields = [
            'name',
            'slug',
            'date_from',
            'date_to',
            'date_admission',
            'is_public',
            'location',
            'geo_lat',
            'geo_lon',
            'email',
        ]
        field_classes = {
            'date_from': SplitDateTimeField,
            'date_to': SplitDateTimeField,
            'date_admission': SplitDateTimeField,
        }
        widgets = {
            'slug': SlugWidget(attrs={'data-slug-source': 'name'}),
            'date_from': SplitDateTimePickerWidget(),
            'date_to': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_date_from_0'}),
            'date_admission': SplitDateTimePickerWidget(attrs={'data-date-default': '#id_date_from_0'}),
        }
