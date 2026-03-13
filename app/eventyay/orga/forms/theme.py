"""
Forms for theme configuration in admin/organizer interfaces.

Provides user-friendly forms for managing design tokens and theme settings.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.eventyay_common.models import EventTheme, OrganizerTheme


class BaseThemeForm(forms.ModelForm):
    """Base form for theme configuration."""

    primary_color = forms.CharField(
        label=_('Primary Color'),
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control',
            'help_text': _('Organization or event brand color'),
        }),
        help_text=_('Main brand color (e.g., #EB2188)'),
    )

    secondary_color = forms.CharField(
        label=_('Secondary Color'),
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control',
        }),
        help_text=_('Secondary accent color'),
    )

    class Meta:
        fields = ['color_mode', 'is_active', 'description']
        widgets = {
            'color_mode': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': _('Internal notes about this theme...'),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure token_overrides is initialized as dict
        if self.instance and not getattr(self.instance, 'pk', None):
            self.instance.token_overrides = self.instance.token_overrides or {}
        # Populate synthetic fields from token_overrides on initial render.
        if not self.is_bound and self.instance:
            primary = self.instance.get_primary_color()
            secondary = self.instance.get_secondary_color()
            self.fields['primary_color'].initial = primary if primary else '#EB2188'
            self.fields['secondary_color'].initial = secondary if secondary else '#3B82F6'

    def clean_primary_color(self) -> str | None:
        """Validate primary color format."""
        color = self.cleaned_data.get('primary_color', '')
        if color and not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format. Use hex format (e.g., #FF0000)'))
        return color

    def clean_secondary_color(self) -> str | None:
        """Validate secondary color format."""
        color = self.cleaned_data.get('secondary_color', '')
        if color and not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format. Use hex format (e.g., #FF0000)'))
        return color

    @staticmethod
    def _is_valid_color(color: str) -> bool:
        """Check if color is valid hex format."""
        import re
        return bool(re.match(r'^#[0-9A-Fa-f]{6}$', color))

    def save(self, commit: bool = True):
        """Save form and update token overrides."""
        instance = super().save(commit=False)

        # Ensure token_overrides is a dict
        if not isinstance(instance.token_overrides, dict):
            instance.token_overrides = {}

        # Update primary color in token overrides
        primary = self.cleaned_data.get('primary_color')
        if primary:
            if 'colors' not in instance.token_overrides:
                instance.token_overrides['colors'] = {}
            instance.token_overrides['colors']['primary'] = primary

        # Update secondary color in token overrides
        secondary = self.cleaned_data.get('secondary_color')
        if secondary:
            if 'colors' not in instance.token_overrides:
                instance.token_overrides['colors'] = {}
            instance.token_overrides['colors']['secondary'] = secondary

        if commit:
            instance.save()
        return instance


class OrganizerThemeForm(BaseThemeForm):
    """Form for customizing organizer-level theme."""

    logo_url = forms.URLField(
        label=_('Logo URL'),
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': _('https://example.com/logo.png'),
        }),
    )

    favicon_url = forms.URLField(
        label=_('Favicon URL'),
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': _('https://example.com/favicon.ico'),
        }),
    )

    class Meta(BaseThemeForm.Meta):
        model = OrganizerTheme
        fields = BaseThemeForm.Meta.fields + ['logo_url', 'favicon_url']


class EventThemeForm(BaseThemeForm):
    """Form for customizing event-level theme."""

    inherit_organizer_theme = forms.BooleanField(
        label=_('Inherit Organizer Theme'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Apply organizer branding and colors to this event'),
    )

    custom_css = forms.CharField(
        label=_('Custom CSS'),
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': _('/* Add custom CSS rules for this event */\n.custom-class { color: red; }'),
            'data-editor': 'css',
        }),
        help_text=_('Additional custom CSS rules applied to this event only'),
    )

    class Meta(BaseThemeForm.Meta):
        model = EventTheme
        fields = BaseThemeForm.Meta.fields + ['inherit_organizer_theme', 'custom_css']

    def clean_custom_css(self) -> str:
        """Validate CSS syntax."""
        css = self.cleaned_data.get('custom_css', '')
        # Basic validation - just check for balanced braces
        if css:
            open_braces = css.count('{')
            close_braces = css.count('}')
            if open_braces != close_braces:
                raise ValidationError(_('CSS syntax error: unbalanced braces'))
        return css


class TokenImportForm(forms.Form):
    """Form for importing theme configuration from JSON."""

    json_file = forms.FileField(
        label=_('JSON File'),
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.json',
        }),
        help_text=_('Upload a JSON file containing theme configuration'),
    )

    override_existing = forms.BooleanField(
        label=_('Override Existing Theme'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Replace existing theme settings with imported configuration'),
    )

    def clean_json_file(self):
        """Validate JSON file format."""
        json_file = self.cleaned_data.get('json_file')
        if json_file:
            import json
            try:
                content = json_file.read().decode('utf-8')
                json.loads(content)
            except json.JSONDecodeError:
                raise ValidationError(_('Invalid JSON file. Please check the file format.'))
            except UnicodeDecodeError:
                raise ValidationError(_('File must be in UTF-8 encoding.'))
        return json_file


class QuickThemeForm(forms.Form):
    """Quick theme customization form (simplified for admin interfaces)."""

    name = forms.CharField(
        label=_('Theme Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('e.g., Winter 2024'),
        }),
    )

    primary_color = forms.CharField(
        label=_('Primary Color'),
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control form-control-color',
        }),
        initial='#EB2188',
    )

    secondary_color = forms.CharField(
        label=_('Secondary Color'),
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control form-control-color',
        }),
        initial='#3B82F6',
    )

    text_color = forms.CharField(
        label=_('Text Color'),
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control form-control-color',
        }),
        initial='#111827',
    )

    background_color = forms.CharField(
        label=_('Background Color'),
        widget=forms.TextInput(attrs={
            'type': 'color',
            'class': 'form-control form-control-color',
        }),
        initial='#FFFFFF',
    )

    color_mode = forms.ChoiceField(
        label=_('Color Mode'),
        choices=[
            ('light', _('Light')),
            ('dark', _('Dark')),
            ('auto', _('Auto (System Preference)')),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='auto',
    )

    def clean_primary_color(self) -> str:
        """Validate primary color."""
        color = self.cleaned_data.get('primary_color', '')
        if not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format'))
        return color

    def clean_secondary_color(self) -> str:
        """Validate secondary color."""
        color = self.cleaned_data.get('secondary_color', '')
        if not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format'))
        return color

    def clean_text_color(self) -> str:
        """Validate text color."""
        color = self.cleaned_data.get('text_color', '')
        if not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format'))
        return color

    def clean_background_color(self) -> str:
        """Validate background color."""
        color = self.cleaned_data.get('background_color', '')
        if not self._is_valid_color(color):
            raise ValidationError(_('Invalid color format'))
        return color

    @staticmethod
    def _is_valid_color(color: str) -> bool:
        """Check if color is valid hex format."""
        import re
        return bool(re.match(r'^#[0-9A-Fa-f]{6}$', color))

    def get_token_overrides(self) -> dict:
        """Convert form data to token overrides."""
        if not self.is_valid():
            return {}

        return {
            'colors': {
                'primary': self.cleaned_data['primary_color'],
                'secondary': self.cleaned_data['secondary_color'],
                'text': self.cleaned_data['text_color'],
                'background': self.cleaned_data['background_color'],
            },
        }
