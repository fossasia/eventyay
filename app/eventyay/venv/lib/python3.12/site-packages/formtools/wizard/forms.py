from django import forms


class ManagementForm(forms.Form):
    """
    ``ManagementForm`` is used to keep track of the current wizard step.
    """
    template_name = "django/forms/p.html"  # Remove when Django 5.0 is minimal version.
    current_step = forms.CharField(widget=forms.HiddenInput)
