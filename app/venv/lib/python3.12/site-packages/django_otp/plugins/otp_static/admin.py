from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.contrib.auth import get_user_model

from django_otp.admin import user_model_search_fields
from django_otp.conf import settings

from .models import StaticDevice, StaticToken


class StaticTokenInline(admin.TabularInline):
    model = StaticToken
    extra = 0


class StaticDeviceAdmin(admin.ModelAdmin):
    """
    :class:`~django.contrib.admin.ModelAdmin` for
    :class:`~django_otp.plugins.otp_static.models.StaticDevice`.
    """

    User = get_user_model()
    candidate_search_field = [User.USERNAME_FIELD, 'email']

    list_display = ['user', 'name', 'created_at', 'last_used_at', 'confirmed']
    list_filter = ['created_at', 'last_used_at', 'confirmed']
    search_fields, search_help_text = user_model_search_fields(candidate_search_field)

    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'last_used_at']

    fieldsets = [
        (
            'Identity',
            {
                'fields': ['user', 'name', 'confirmed'],
            },
        ),
        (
            'Timestamps',
            {
                'fields': ['created_at', 'last_used_at'],
            },
        ),
    ]

    inlines = [
        StaticTokenInline,
    ]

    def get_inline_instances(self, request, obj=None):
        if settings.OTP_ADMIN_HIDE_SENSITIVE_DATA and obj:
            return []
        return super().get_inline_instances(request, obj)


# Somehow this is getting imported twice, triggering a useless exception.
try:
    admin.site.register(StaticDevice, StaticDeviceAdmin)
except AlreadyRegistered:
    pass
