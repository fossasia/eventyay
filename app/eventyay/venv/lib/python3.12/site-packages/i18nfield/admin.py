from django.contrib.admin import ModelAdmin

from . import fields, forms


class I18nModelAdmin(ModelAdmin):
    formfield_overrides_defaults = {
        fields.I18nTextField: {"widget": forms.I18nTextarea},
        fields.I18nCharField: {"widget": forms.I18nTextInput},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ensure django admin uses the special i18n widges, but allow child
        # classes to override them using formfield_overrides_defaults.
        for k, v in self.formfield_overrides_defaults.items():
            self.formfield_overrides.setdefault(k, v)
