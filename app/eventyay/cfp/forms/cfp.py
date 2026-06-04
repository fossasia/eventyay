import logging

from django.core.exceptions import ValidationError
from django.forms.utils import ErrorDict
from django.utils.translation import gettext_lazy as _

from eventyay.common.language import language

logger = logging.getLogger(__name__)


class CfPFormMixin:
    """All forms used in the CfP step process should use this mixin.

    It serves to make it work with the CfP Flow editor, e.g. by allowing
    users to change help_text attributes of fields. Needs to go first
    before all other forms changing help_text behaviour.
    """

    NON_STRICT_ERROR_CODES = {'required', 'blank', 'incomplete'}
    NON_STRICT_ERROR_MESSAGES = (
        _('This field is required.'),
        _('This field cannot be blank.'),
        _('This field may not be blank.'),
        _('Enter a complete value.'),
    )

    def __init__(self, *args, field_configuration=None, not_strict=False, draft_save=False, **kwargs):
        self.not_strict = not_strict
        self.draft_save = draft_save
        super().__init__(*args, **kwargs)
        self.field_configuration = field_configuration
        if self.field_configuration:
            self.field_configuration = {field_data['key']: field_data for field_data in field_configuration}
            for field_data in self.field_configuration:
                if field_data in self.fields:
                    self._update_cfp_texts(field_data)

    def full_clean(self):
        original_required = {}
        if self.not_strict:
            for name, field in self.fields.items():
                original_required[name] = field.required
                field.required = False
                if hasattr(field.widget, 'is_required'):
                    field.widget.is_required = False
        try:
            super().full_clean()
        finally:
            for name, required in original_required.items():
                field = self.fields.get(name)
                if not field:
                    continue
                field.required = required
                if hasattr(field.widget, 'is_required'):
                    field.widget.is_required = required

        if self.not_strict:
            self._scrub_non_strict_errors()

    def _scrub_non_strict_errors(self):
        if not self._errors:
            return

        scrubbed_errors = ErrorDict(renderer=self._errors.renderer)
        for field_name, error_list in self._errors.items():
            filtered_errors = self._scrub_validation_errors(error_list.as_data())
            if filtered_errors:
                scrubbed_errors[field_name] = error_list.__class__(
                    filtered_errors,
                    error_class=error_list.error_class.removeprefix('errorlist ').strip() or None,
                    renderer=error_list.renderer,
                    field_id=error_list.field_id,
                )
        self._errors = scrubbed_errors

    def _scrub_validation_errors(self, errors):
        scrubbed_errors = []
        for error in errors:
            scrubbed = self._scrub_validation_error(error)
            if scrubbed is not None:
                scrubbed_errors.append(scrubbed)
        return scrubbed_errors

    def _scrub_validation_error(self, error):
        if not isinstance(error, ValidationError):
            return error
        if hasattr(error, 'message'):
            if self._is_non_strict_error(error):
                return None
            return error
        if hasattr(error, 'error_dict'):
            scrubbed_dict = {}
            for key, values in error.error_dict.items():
                scrubbed_values = self._scrub_validation_errors(values)
                if scrubbed_values:
                    scrubbed_dict[key] = scrubbed_values
            return ValidationError(scrubbed_dict) if scrubbed_dict else None

        scrubbed_list = self._scrub_validation_errors(error.error_list)
        return ValidationError(scrubbed_list) if scrubbed_list else None

    def _is_non_strict_error(self, error):
        if error.code in self.NON_STRICT_ERROR_CODES:
            return True
        message = str(getattr(error, 'message', ''))
        return any(message == str(candidate) for candidate in self.NON_STRICT_ERROR_MESSAGES)

    def _update_cfp_texts(self, field_name):
        field = self.fields.get(field_name)
        if not field or not self.field_configuration:
            return
        field_data = self.field_configuration.get(field_name) or {}
        field.original_help_text = field_data.get('help_text') or ''
        if field.original_help_text:
            from eventyay.base.templatetags.rich_text import rich_text

            field.help_text = rich_text(
                str(field.original_help_text) + ' ' + str(getattr(field, 'added_help_text', ''))
            )
        stored_label = field_data.get('label')
        if stored_label:
            # Preserve explicit organizer customizations, but avoid pinning cached
            # gettext fallbacks that can block future PO/MO updates.
            label_data = getattr(stored_label, 'data', None)
            if label_data:
                english = label_data.get('en', '')
                has_real_translation = any(
                    v and v != english for k, v in label_data.items() if k != 'en'
                )
                with language('en'):
                    default_english_label = str(field.label or '')
                has_custom_english = bool(english) and english != default_english_label
            else:
                has_real_translation = True
                has_custom_english = False
            if has_real_translation or has_custom_english:
                field.label = stored_label
