import logging
from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.crypto import get_random_string
from django.utils.text import normalize_newlines
from django.utils.translation import gettext_lazy as _

from hierarkey.models import BaseHierarkeyStoreModel

logger = logging.getLogger(__name__)


class HierarkeyForm(forms.Form):
    """
    This is a custom subclass of ``django.forms.Form`` that you can use to set
    values for any keys. See the Forms chapter of the documentation for more details.
    """
    BOOL_CHOICES = (
        ('False', _('disabled')),
        ('True', _('enabled')),
    )

    def __init__(self, *args, obj, attribute_name, **kwargs):
        self.obj = obj
        self.attribute_name = attribute_name
        self._s = getattr(obj, attribute_name)
        initial = kwargs.pop('initial', {})
        initial.update(self._s.freeze())
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def save(self) -> None:
        """
        Saves all changed values to the database.
        """
        for name, field in self.fields.items():
            value = self.cleaned_data[name]
            if isinstance(value, UploadedFile):
                # Delete old file
                fname = self._s.get(name, as_type=File)
                if fname and self.__file_is_last_reference(name, self._s.get(name, as_type=str)):
                    try:
                        default_storage.delete(fname.name)
                    except OSError:  # pragma: no cover
                        logger.error('Deleting file %s failed.' % fname.name)

                # Create new file
                newname = default_storage.save(self.get_new_filename(value.name), value)
                value._name = newname
                self._s.set(name, value)
            elif isinstance(value, File):
                # file is unchanged
                continue
            elif not value and isinstance(field, forms.FileField):
                # file is deleted
                fname = self._s.get(name, as_type=File)
                if fname and self.__file_is_last_reference(name, self._s.get(name, as_type=str)):
                    try:
                        default_storage.delete(fname.name)
                    except OSError:  # pragma: no cover
                        logger.error('Deleting file %s failed.' % fname.name)
                del self._s[name]
            elif value is None:
                del self._s[name]
            elif type(value) is str:
                if normalize_newlines(self._s.get(name, as_type=str)) != normalize_newlines(value):
                    self._s.set(name, value)
            elif self._s.get(name, as_type=type(value)) != value:
                self._s.set(name, value)

    def __file_is_last_reference(self, key, value):
        for klass in BaseHierarkeyStoreModel.__subclasses__():
            if klass._meta.abstract:
                continue
            qs = klass.objects.filter(key=key, value=value)
            try:
                if isinstance(self.obj, klass._meta.get_field('object').remote_field.model):
                    qs = qs.exclude(object=self.obj)
            except FieldDoesNotExist:
                pass
            print(klass, qs)
            if qs.exists():
                print("false", qs, self.obj, klass)
                return False
        return True

    def get_new_filename(self, name: str) -> str:
        """
        Returns the file name to use based on the original filename of an uploaded file.
        By default, the file name is constructed as::

            <model_name>-<attribute_name>/<primary_key>/<original_basename>.<random_nonce>.<extension>
        """
        nonce = get_random_string(length=8)
        return '%s-%s/%s/%s.%s.%s' % (
            self.obj._meta.model_name, self.attribute_name,
            self.obj.pk, name, nonce, name.split('.')[-1]
        )
