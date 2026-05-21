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
from eventyay.common.forms.mixins import JsonSubfieldMixin
from eventyay.common.language import get_language_choices_native_with_ui_name
from eventyay.common.urls import get_file_url_path, is_http_url, normalize_url_scheme
from eventyay.control.forms import SlugWidget, SplitDateTimeField, SplitDateTimePickerWidget
from eventyay.multidomain.models import KnownDomain
from eventyay.orga.forms.widgets import MultipleLanguagesWidget


def is_external_image_url(value: str) -> bool:
    return is_http_url(value)


class EventCommonSettingsForm(SettingsForm):
    event_logo_image_url = forms.URLField(
        label=_('Logo URL'),
        required=False,
        help_text=_('Use an external image URL instead of uploading a logo file.'),
    )
    logo_image_url = forms.URLField(
        label=_('Header image URL'),
        required=False,
        help_text=_('Use an external image URL instead of uploading a header image file.'),
    )
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )

    image_url_fields = {
        'event_logo_image': 'event_logo_image_url',
        'logo_image': 'logo_image_url',
    }

    @property
    def image_source_states(self):
        states = {}
        for image_field in self.image_url_fields:
            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            states[image_field] = {
                'has_uploaded_file': bool(current_value and not is_external_image_url(current_value)),
            }
        return states

    auto_fields = [
        'locales',
        'content_locales',
        'locale',
        'region',
        'imprint_url',
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'logo_show_title',
        'og_image',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'frontpage_text',
    ]

    def clean(self):
        data = super().clean()

        for image_field, url_field in self.image_url_fields.items():
            image_url = data.get(url_field) or ''
            submitted_image = self.fields[image_field].widget.value_from_datadict(
                self.data,
                self.files,
                self.add_prefix(image_field),
            )
            has_new_upload = isinstance(submitted_image, UploadedFile)
            if image_url and has_new_upload:
                message = _('Either upload a file or enter an external URL, not both.')
                self.add_error(image_field, message)
                self.add_error(url_field, message)
                continue

            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            if image_url:
                data[image_field] = normalize_url_scheme(image_url)
            elif is_external_image_url(current_value) and not has_new_upload:
                data[image_field] = None

        settings_dict = self.get_initial_settings()
        settings_dict.update({k: v for k, v in data.items() if k not in self.image_url_fields.values()})
        validate_event_settings(self.event, settings_dict)
        return data

    def save(self):
        for image_field, url_field in self.image_url_fields.items():
            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            new_value = self.cleaned_data.get(image_field)
            if is_external_image_url(current_value) and (isinstance(new_value, UploadedFile) or not new_value):
                del self.event.settings[image_field]
            current_file = get_file_url_path(current_value)
            if type(new_value) is str and current_file and current_value != new_value:
                default_storage.delete(current_file)
            self.cleaned_data[url_field] = None
        return super().save()

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)
        for image_field, url_field in self.image_url_fields.items():
            current_value = self.event.settings.get(image_field, as_type=str, default='') or ''
            if is_external_image_url(current_value):
                self.initial[image_field] = None
                self.initial[url_field] = current_value
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


class EventPublicationForm(JsonSubfieldMixin, forms.Form):
    meta_noindex = forms.BooleanField(
        label=_('Ask search engines not to index this event’s public pages, including ticket shop pages'),
        help_text=_(
            'When enabled, a noindex/nofollow robots meta tag is added to this event’s public pages, including '
            'schedule, talk, and ticket shop pages, asking search engines not to index them.'
        ),
        required=False,
    )
    exclude_from_start_page = forms.BooleanField(
        label=_('Exclude this event from start pages'),
        help_text=_(
            'When enabled, this event will not appear in the public event listings on the platform or '
            'organizer start pages.'
        ),
        required=False,
    )
    exclude_from_search = forms.BooleanField(
        label=_('Exclude this event from platform search results'),
        help_text=_(
            'When enabled, this event will not appear in platform-wide event search results.'
        ),
        required=False,
    )

    class Meta:
        json_fields = {
            'meta_noindex': 'display_settings',
            'exclude_from_start_page': 'display_settings',
            'exclude_from_search': 'display_settings',
        }

    def save(self, *args, **kwargs):
        commit = kwargs.pop('commit', True)
        instance = super().save(*args, commit=False, **kwargs)
        update_fields = list({path for path in self.Meta.json_fields.values()})
        exclude_from_start_page = self.cleaned_data.get('exclude_from_start_page', False)
        if exclude_from_start_page:
            if instance.startpage_visible:
                instance.startpage_visible = False
                update_fields.append('startpage_visible')
            if instance.startpage_featured:
                instance.startpage_featured = False
                update_fields.append('startpage_featured')
        elif instance.live and not instance.has_component_testmode and not instance.startpage_visible:
            instance.startpage_visible = True
            update_fields.append('startpage_visible')
        if commit:
            instance.save(update_fields=list(dict.fromkeys(update_fields)))
        return instance
