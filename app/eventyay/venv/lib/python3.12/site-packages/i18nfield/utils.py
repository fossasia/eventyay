from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet

from .strings import LazyI18nString


class I18nJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, LazyI18nString):
            return obj.data
        elif isinstance(obj, QuerySet):
            return list(obj)
        elif isinstance(obj, Model):
            return {'type': obj.__class__.__name__, 'id': obj.id}
        else:
            return super().default(obj)
