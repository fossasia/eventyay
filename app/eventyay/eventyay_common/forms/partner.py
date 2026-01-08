from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Partner, SponsorGroup


class SponsorGroupForm(forms.ModelForm):
    """Form for creating and editing sponsor groups"""
    
    class Meta:
        model = SponsorGroup
        fields = ['name', 'order', 'logo_size']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Platinum Sponsor, Gold Sponsor')
            }),
            'order': forms.HiddenInput(),
            'logo_size': forms.NumberInput(attrs={
                'class': 'form-control logo-size-input',
                'min': 20,
                'max': 500,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)
    
    def clean_name(self):
        """Validate that group name is unique within the event"""
        name = self.cleaned_data.get('name')
        if not name:
            return name
        
        # Check if another group with this name exists in the same event
        queryset = SponsorGroup.objects.filter(event=self.event, name__iexact=name)
        
        # Exclude current instance if editing
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise forms.ValidationError(
                _('A sponsor group with this name already exists for this event. Please choose a different name.')
            )
        
        return name


class PartnerForm(forms.ModelForm):
    """Form for creating and editing partners within a sponsor group"""
    
    class Meta:
        model = Partner
        fields = ['name', 'link', 'logo', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Partner name')
            }),
            'link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com')
            }),
            'order': forms.HiddenInput(),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
    
    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Validate file size (max 10MB as per requirements)
            if logo.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    _('Logo file size must not exceed 10MB')
                )
            # Validate file type
            valid_extensions = ['.gif', '.jpeg', '.jpg', '.png', '.svg']
            ext = logo.name.lower().split('.')[-1]
            if f'.{ext}' not in valid_extensions:
                raise forms.ValidationError(
                    _('Supported formats: gif, jpeg, jpg, png, svg')
                )
        return logo


class BasePartnerFormSet(BaseInlineFormSet):
    """Base formset for partners with custom validation"""
    
    def clean(self):
        """Validate that at least one partner has a name if formset is not being deleted"""
        if any(self.errors):
            return
        
        names = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                name = form.cleaned_data.get('name')
                if name:
                    names.append(name)
        
        # Allow empty formsets (no partners in group is valid)
        return


# Inline formset for managing partners within a sponsor group
PartnerFormSet = inlineformset_factory(
    SponsorGroup,
    Partner,
    form=PartnerForm,
    formset=BasePartnerFormSet,
    extra=1,  # Show 1 empty form, user can add more dynamically
    can_delete=True,
    can_order=True,
)
