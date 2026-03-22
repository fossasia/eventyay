from typing import List, Union

import copy
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import (
    BaseForm, BaseInlineFormSet, BaseModelForm, BaseModelFormSet,
)
from django.forms.forms import DeclarativeFieldsMetaclass
from django.forms.models import ModelFormMetaclass
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .strings import LazyI18nString


class I18nWidget(forms.MultiWidget):
    """
    The default form widget for I18nCharField and I18nTextField. It makes
    use of Django's MultiWidget mechanism and does some magic to save you
    time.
    """
    widget = forms.TextInput

    def __init__(self, locales: List[str], field: forms.Field, attrs=None):
        widgets = []
        self.locales = locales
        self.enabled_locales = locales
        self.field = field
        for lng in self.locales:
            a = copy.copy(attrs) or {}
            a['lang'] = lng
            a['dir'] = 'ltr' if lng not in settings.LANGUAGES_BIDI else 'rtl'
            widgets.append(self.widget(attrs=a))
        super().__init__(widgets, attrs)

    def decompress(self, value) -> List[Union[str, None]]:
        data = []
        first_enabled = None
        any_enabled_filled = False
        if not isinstance(value, LazyI18nString):
            value = LazyI18nString(value)
        for i, lng in enumerate(self.locales):
            dataline = (
                value.data[lng]
                if value is not None and (
                    isinstance(value.data, dict) or isinstance(value.data, LazyI18nString.LazyGettextProxy)
                ) and lng in value.data
                else None
            )
            if lng in self.enabled_locales:
                if not first_enabled:
                    first_enabled = i
                if dataline:
                    any_enabled_filled = True
            data.append(dataline)
        if value and not isinstance(value.data, dict) and not isinstance(value.data, LazyI18nString.LazyGettextProxy):
            data[first_enabled] = value.data
        elif value and not any_enabled_filled:
            data[first_enabled] = value.localize(self.enabled_locales[0])
        return data

    def render(self, name: str, value, attrs=None, renderer=None) -> str:
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list of values, each corresponding to a widget
        # in self.widgets.

        original_value = value

        if not isinstance(value, list):
            value = self.decompress(value)
        output = []
        final_attrs = self.build_attrs(attrs or dict())
        id_ = final_attrs.get('id', None)
        for i, widget in enumerate(self.widgets):
            if self.locales[i] not in self.enabled_locales:
                continue
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None

            if not widget_value and isinstance(original_value, LazyI18nString) and isinstance(original_value.data, dict):
                locale = self.locales[i]
                firstpart = locale.split('-')[0]

                if not widget_value:
                    similar = [
                        loc for loc in self.locales
                        if (loc.startswith(firstpart + "-") or firstpart == loc) and loc != locale
                    ]
                    for s in similar:
                        if original_value.data.get(s) and s not in self.enabled_locales:
                            widget_value = original_value.data.get(s)
                            break

            final_attrs_widget = final_attrs.copy()
            if id_:
                human_locale_name = dict(settings.LANGUAGES).get(self.locales[i], self.locales[i])
                final_attrs_widget['id'] = '%s_%s' % (id_, i)
                final_attrs_widget['title'] = human_locale_name
                # still allow forms to override the placeholder
                final_attrs_widget.setdefault('placeholder', human_locale_name)
            output.append(widget.render(name + '_%s' % i, widget_value, final_attrs_widget, renderer=renderer))
        return mark_safe(self.format_output(output, id_))

    def format_output(self, rendered_widgets, id_) -> str:
        return '<div class="i18n-form-group%s" id="%s">%s</div>' % (
            ' i18n-form-single-language' if len(rendered_widgets) <= 1 else '',
            escape(id_),
            ''.join(rendered_widgets),
        )


class I18nTextInput(I18nWidget):
    """
    The default form widget for I18nCharField. It makes use of Django's MultiWidget
    mechanism and does some magic to save you time.
    """
    widget = forms.TextInput


class I18nTextarea(I18nWidget):
    """
    The default form widget for I18nTextField. It makes use of Django's MultiWidget
    mechanism and does some magic to save you time.
    """
    widget = forms.Textarea


class I18nFormField(forms.MultiValueField):
    """
    The form field that is used by I18nCharField and I18nTextField. It makes use
    of Django's MultiValueField mechanism to create one sub-field per available
    language.

    It contains special treatment to make sure that a field marked as "required" is validated
    as "filled out correctly" if *at least one* translation is filled it. It is never required
    to fill in all of them. This has the drawback that the HTML property ``required`` is set on
    none of the fields as this would lead to irritating behaviour.

    :param locales: An iterable of locale codes that the widget should render a field for. If
                    omitted, fields will be rendered for all languages configured in
                    ``settings.LANGUAGES``.
    :param require_all_fields: A boolean, if set to True field requires all translations to be given.
    """

    def compress(self, data_list) -> LazyI18nString:
        locales = self.locales
        data = {}
        for i, value in enumerate(data_list):
            data[locales[i]] = value
        return LazyI18nString(data)

    def clean(self, value) -> LazyI18nString:
        if isinstance(value, LazyI18nString):
            # This happens e.g. if the field is disabled
            return value
        found = False
        found_all = True
        clean_data = []
        errors = []
        for i, field in enumerate(self.fields):
            try:
                field_value = value[i]
            except (IndexError, TypeError):
                field_value = None
            if field_value not in self.empty_values:
                found = True
            elif field.locale in self.widget.enabled_locales:
                found_all = False
            try:
                clean_data.append(field.clean(field_value))
            except forms.ValidationError as e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter. Skip duplicates.
                errors.extend(m for m in e.error_list if m not in errors)
        if errors:
            raise forms.ValidationError(errors)
        if self.one_required and not found:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        if self.require_all_fields and not found_all:
            raise forms.ValidationError(self.error_messages['incomplete'], code='incomplete')

        out = self.compress(clean_data)
        self.validate(out)
        self.run_validators(out)
        return out

    def __init__(self, *args, **kwargs):
        fields = []
        defaults = {
            'widget': self.widget,
            'max_length': kwargs.pop('max_length', None),
        }
        self.locales = kwargs.pop('locales', [loc[0] for loc in settings.LANGUAGES])
        self.one_required = kwargs.get('required', True)
        require_all_fields = kwargs.pop('require_all_fields', False)
        kwargs['required'] = False
        kwargs['widget'] = kwargs['widget'](
            locales=self.locales, field=self, **kwargs.pop('widget_kwargs', {})
        )
        defaults.update(**kwargs)
        for lngcode in self.locales:
            defaults['label'] = '%s (%s)' % (defaults.get('label'), lngcode)
            field = forms.CharField(**defaults)
            field.locale = lngcode
            fields.append(field)
        super().__init__(
            fields=fields, require_all_fields=False, *args, **kwargs
        )
        self.require_all_fields = require_all_fields

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if initial is None:
            initial = ['' for x in range(0, len(data))]
        else:
            if not isinstance(initial, list):
                initial = self.widget.decompress(initial)
        for field, initial, data in zip(self.fields, initial, data):
            if field.locale not in self.widget.enabled_locales:
                continue
            try:
                initial = field.to_python(initial)
            except ValidationError:
                return True
            if field.has_changed(initial, data):
                return True
        return False


class I18nFormMixin:
    def __init__(self, *args, **kwargs):
        locales = kwargs.pop('locales', None)
        super().__init__(*args, **kwargs)
        if locales:
            for k, field in self.fields.items():
                if isinstance(field, I18nFormField):
                    field.widget.enabled_locales = locales


class BaseI18nModelForm(I18nFormMixin, BaseModelForm):
    """
    This is a helperclass to construct an I18nModelForm.
    """
    pass


class BaseI18nForm(I18nFormMixin, BaseForm):
    """
    This is a helperclass to construct an I18nForm.
    """
    pass


class I18nForm(BaseI18nForm, metaclass=DeclarativeFieldsMetaclass):
    """
    This is a modified version of Django's Form which differs from Form in
    only one way: The constructor takes one additional optional argument ``locales``
    expecting a list of language codes. If given, this instance is used to select
    the visible languages in all I18nFormFields of the form. If not given, all languages
    from ``settings.LANGUAGES`` will be displayed.

    :param locales: A list of locales that should be displayed.
    """
    pass


class I18nModelForm(BaseI18nModelForm, metaclass=ModelFormMetaclass):
    """
    This is a modified version of Django's ModelForm which differs from ModelForm in
    only one way: The constructor takes one additional optional argument ``locales``
    expecting a list of language codes. If given, this instance is used to select
    the visible languages in all I18nFormFields of the form. If not given, all languages
    from ``settings.LANGUAGES`` will be displayed.

    :param locales: A list of locales that should be displayed.
    """
    pass


class I18nFormSetMixin:

    def __init__(self, *args, **kwargs):
        self.locales = kwargs.pop('locales', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['locales'] = self.locales
        return super()._construct_form(i, **kwargs)

    @property
    def empty_form(self):
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            locales=self.locales,
            **self.get_form_kwargs(None),
        )
        self.add_fields(form, None)
        return form


class I18nModelFormSet(I18nFormSetMixin, BaseModelFormSet):
    """
    This is equivalent to a normal BaseModelFormset, but cares for the special needs
    of I18nForms (see there for more information).

    :param locales: A list of locales that should be displayed.
    """
    pass


class I18nInlineFormSet(I18nFormSetMixin, BaseInlineFormSet):
    """
    This is equivalent to a normal BaseInlineFormset, but cares for the special needs
    of I18nForms (see there for more information).

    :param locales: A list of locales that should be displayed.
    """
    pass
