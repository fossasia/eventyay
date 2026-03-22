from django.contrib import admin
from .views import login_view


admin.autodiscover()
admin.site.login = login_view
