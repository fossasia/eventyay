from django.forms import ModelChoiceField, ModelMultipleChoiceField


class SafeModelChoiceField(ModelChoiceField):
    def __init__(self, queryset, **kwargs):
        queryset = queryset.model.objects.none()
        super().__init__(queryset, **kwargs)


class SafeModelMultipleChoiceField(ModelMultipleChoiceField):
    def __init__(self, queryset, **kwargs):
        queryset = queryset.model.objects.none()
        super().__init__(queryset, **kwargs)
