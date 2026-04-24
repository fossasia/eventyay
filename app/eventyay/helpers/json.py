from django.core.files import File
from i18nfield.utils import I18nJSONEncoder
from phonenumber_field.phonenumber import PhoneNumber

from eventyay.base.reldate import RelativeDateWrapper
from eventyay.common.utils.masks import EmailMasker


class CustomJSONEncoder(I18nJSONEncoder):
    def default(self, obj):
        if isinstance(obj, RelativeDateWrapper):
            return obj.to_string()
        elif isinstance(obj, File):
            return obj.name
        elif isinstance(obj, EmailMasker):
            return obj.to_json()
        if isinstance(obj, PhoneNumber):
            return str(obj)
        else:
            return super().default(obj)


def safe_string(original):
    return original.replace('<', '\\u003C').replace('>', '\\u003E')
