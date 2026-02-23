import logging

logger = logging.getLogger(__name__)


class CfPFormMixin:
    """All forms used in the CfP step process should use this mixin.

    It serves to make it work with the CfP Flow editor, e.g. by allowing
    users to change help_text attributes of fields. Needs to go first
    before all other forms changing help_text behaviour.
    """

    def __init__(self, *args, field_configuration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_configuration = field_configuration
        if self.field_configuration:
            self.field_configuration = {field_data['key']: field_data for field_data in field_configuration}
            for field_data in self.field_configuration:
                if field_data in self.fields:
                    self._update_cfp_texts(field_data)

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
            # Only apply the stored label if it contains at least one translation
            # that genuinely differs from the English string. A label where every
            # locale maps to the same English text is a cached gettext fallback —
            # the field's own gettext_lazy verbose_name is more reliable.
            label_data = getattr(stored_label, 'data', None)
            if label_data:
                english = label_data.get('en', '')
                has_real_translation = any(
                    v and v != english for k, v in label_data.items() if k != 'en'
                )
            else:
                has_real_translation = False
            if has_real_translation:
                field.label = stored_label
