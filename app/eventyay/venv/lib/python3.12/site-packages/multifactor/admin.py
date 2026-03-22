from django.contrib import admin
from django.db.models import OuterRef, Exists

from .models import UserKey


class HasMultifactorFilter(admin.SimpleListFilter):
    title = 'Using Multifactor authentication?'
    parameter_name = 'multifactor'

    def lookups(self, request, model_admin):
        return [
            (True, 'Yes'),
            (False, 'No'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(has_multifactors=self.value())


class MultiFactorInline(admin.TabularInline):
    model = UserKey
    readonly_fields = ('key_type',)
    fields = ('key_type', 'enabled')
    max_num = 0


class MultifactorUserAdmin(admin.ModelAdmin):
    multifactor_filter = True
    multifactor_list_display = True
    multifactor_inline = True

    def get_queryset(self, request):
        keys = UserKey.objects.filter(user=OuterRef('pk'), enabled=True)
        return super().get_queryset(request).annotate(has_multifactors=Exists(keys))

    def get_list_display(self, request):
        if not self.multifactor_list_display:
            return super().get_list_display(request)

        return (
            *super().get_list_display(request),
            'multifactor',
        )

    def get_list_filter(self, request):
        if not self.multifactor_filter:
            return super().get_list_filter(request)

        return (
            *super().get_list_filter(request),
            HasMultifactorFilter,
        )

    def multifactor(self, obj):
        return obj.has_multifactors
    multifactor.admin_order_field = 'has_multifactors'
    multifactor.boolean = True

    def get_inline_instances(self, request, obj=None):
        if self.multifactor_inline and MultiFactorInline not in self.inlines:
            self.inlines = (
                *self.inlines,
                MultiFactorInline,
            )

        return super().get_inline_instances(request, obj)
