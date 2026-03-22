from django.apps import AppConfig


class MultifactorConfig(AppConfig):
    default = True
    name = 'multifactor'
    verbose_name = 'Multifactor'
    default_auto_field = 'django.db.models.AutoField'
