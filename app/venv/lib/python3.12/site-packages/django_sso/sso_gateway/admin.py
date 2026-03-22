from django.contrib import admin
from .models import Service, AuthenticationRequest


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
	list_display = 'name', 'base_url', 'enabled'
	fields = 'name', 'base_url', 'token', 'enabled'


@admin.register(AuthenticationRequest)
class AuthenticationRequestAdmin(admin.ModelAdmin):
	list_display = (
		'service',
		'user_identy',
		'created_at',
		'used',
	)

	def has_add_permission(self, *args, **kwargs):
		return False

	def has_change_permission(self, *args, **kwargs):
		return False

	def has_delete_permission(self, request, *args, **kwargs):
		return request.user.is_superuser

	list_filter = 'service__name', 'used'
	search_fields = 'user_identy',

