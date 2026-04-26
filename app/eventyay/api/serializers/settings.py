import logging

from django.core.files import File
from django.core.files.storage import default_storage
from django.db.models.fields.files import FieldFile
from hierarkey.proxy import HierarkeyProxy
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from eventyay.api.serializers.fields import UploadedFileField, UploadedFileOrURLField
from eventyay.base.settings import DEFAULTS
from eventyay.common.urls import get_file_url_path


logger = logging.getLogger(__name__)


class SettingsSerializer(serializers.Serializer):
    default_fields = []

    def __init__(self, *args, **kwargs):
        self.changed_data = []
        super().__init__(*args, **kwargs)
        for fname in self.default_fields:
            kwargs = DEFAULTS[fname].get('serializer_kwargs', {})
            if callable(kwargs):
                kwargs = kwargs()
            kwargs.setdefault('required', False)
            kwargs.setdefault('allow_null', True)
            form_kwargs = DEFAULTS[fname].get('form_kwargs', {})
            if callable(form_kwargs):
                form_kwargs = form_kwargs()
            if 'serializer_class' not in DEFAULTS[fname]:
                raise ValidationError(f'{fname} has no serializer class')
            f = DEFAULTS[fname]['serializer_class'](**kwargs)
            f._label = form_kwargs.get('label', fname)
            f._help_text = form_kwargs.get('help_text')
            f.parent = self
            self.fields[fname] = f

    def update(self, instance: HierarkeyProxy, validated_data):
        for attr, value in validated_data.items():
            if isinstance(value, FieldFile):
                if isinstance(self.fields[attr], UploadedFileOrURLField):
                    current_value = instance.get(attr, as_type=str, default=None)
                    current_file = get_file_url_path(current_value)
                    if current_file:
                        try:
                            default_storage.delete(current_file)
                        except OSError:  # pragma: no cover
                            logger.error('Deleting file %s failed.', current_file)
                else:
                    fname = instance.get(attr, as_type=File)
                    if fname:
                        try:
                            default_storage.delete(fname.name)
                        except OSError:  # pragma: no cover
                            logger.error('Deleting file %s failed.', fname.name)

                # Create new file
                newname = default_storage.save(self.get_new_filename(value.name), value)
                instance.set(attr, File(file=value, name=newname))
                self.changed_data.append(attr)
            elif isinstance(self.fields[attr], UploadedFileOrURLField) and type(value) is str:
                current_value = instance.get(attr, as_type=str)
                current_file = get_file_url_path(current_value)
                if current_file:
                    try:
                        default_storage.delete(current_file)
                    except OSError:  # pragma: no cover
                        logger.error('Deleting file %s failed.', current_file)
                if current_value != value:
                    instance.set(attr, value)
                    self.changed_data.append(attr)
            elif isinstance(self.fields[attr], UploadedFileOrURLField) and value is None:
                current_value = instance.get(attr, as_type=str, default=None)
                current_file = get_file_url_path(current_value)
                if current_file:
                    try:
                        default_storage.delete(current_file)
                    except OSError:  # pragma: no cover
                        logger.error('Deleting file %s failed.', current_file)
                if current_value is not None:
                    instance.delete(attr)
                    self.changed_data.append(attr)
            elif isinstance(self.fields[attr], UploadedFileField):
                if value is None:
                    fname = instance.get(attr, as_type=File)
                    if fname:
                        try:
                            default_storage.delete(fname.name)
                        except OSError:  # pragma: no cover
                            logger.error('Deleting file %s failed.', fname.name)
                    instance.delete(attr)
                else:
                    # file is unchanged
                    continue
            elif value is None:
                instance.delete(attr)
                self.changed_data.append(attr)
            elif instance.get(attr, as_type=type(value)) != value:
                instance.set(attr, value)
                self.changed_data.append(attr)
        return instance

    def get_new_filename(self, name: str) -> str:
        raise NotImplementedError()
