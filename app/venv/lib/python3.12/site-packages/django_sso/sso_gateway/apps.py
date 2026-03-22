from typing import List, Union, Set

from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.db.models.base import ModelBase
from django.db.models.fields.related_descriptors import ForwardOneToOneDescriptor, ReverseOneToOneDescriptor, \
    ForwardManyToOneDescriptor, ReverseManyToOneDescriptor
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from . import Settings


class DjangoSsoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_sso.sso_gateway'
    verbose_name = _('Single Sign-On')

    def ready(self):
        self.sso_settings = Settings()
        self.service_model = self.get_model('Service')

        # region Bind signals for models provided in SSO['ADDITIONAL_FIELDS']
        affected_models = self.sso_settings.affected_models_fields.keys()

        model = get_user_model()

        @receiver(pre_save, sender=model)
        def pre_save_proxy(*args, **kwargs):
            self.on_pre_save_user_model(*args, **kwargs)

        @receiver(post_save, sender=model)
        def post_save_proxy(*args, **kwargs):
            self.on_post_save_user_model(*args, **kwargs)

        @receiver(post_delete, sender=model)
        def post_delete_proxy(*args, **kwargs):
            self.on_post_delete_user(*args, **kwargs)

        if len(affected_models) > 0:
            for model in affected_models:
                if model != get_user_model():
                    @receiver(pre_save, sender=model)
                    def pre_save_proxy(*args, **kwargs):
                        self.on_pre_save_related_model(*args, **kwargs)

                    @receiver(post_delete, sender=model)
                    def post_delete_proxy(*args, **kwargs):
                        self.on_post_delete_related_model(*args, **kwargs)
        # endregion

    def on_pre_save_related_model(self, sender: ModelBase, instance, *args, **kwargs):
        """
        When direct related object saved - calculate difference in relations and send to old and to new users new data
        """
        # get direct One2One|FK (from old|new model)  ++++  reverse FK relations of MODEL

        old_direct_related_users_identities = set()
        old_object_version = instance._meta.model.objects.filter(id=instance.id).first()

        if old_object_version:
            old_direct_related_users_identities = self.get_all_related_users(
                instance=old_object_version,
                include_direct_relations=True,
            )

        new_direct_related_users_identities = self.get_all_related_users(
            instance=instance,
            include_direct_relations=True,
        )

        reverse_related_users_identities = self.get_all_related_users(
            instance=instance,
            include_reversed_relations=True
        )

        deleted_from_user_identities = old_direct_related_users_identities - new_direct_related_users_identities

        if len(deleted_from_user_identities) > 0:
            """
            Send null's to all old related users
            """
            self.service_model.cast_event_to_all_services(
                event_name='update_fields',
                to_users=self._get_users_queryset_by_identities(deleted_from_user_identities),
                instance=None
            )

        actual_related_users = new_direct_related_users_identities | reverse_related_users_identities

        if len(actual_related_users):
            """
            Send updation to all current related users to modified/created object
            """
            self.service_model.cast_event_to_all_services(
                event_name='update_fields',
                to_users=self._get_users_queryset_by_identities(actual_related_users),
                instance=instance
            )

    def on_post_delete_related_model(self, sender: ModelBase, instance, *args, **kwargs):
        """
        Emit event to all related users before model deletion: send nulls.
        """
        related_users = self.get_all_related_users(instance)

        self.service_model.cast_event_to_all_services('update_fields', to_users=related_users, instance=None)

    def get_all_related_users(
            self,
            instance: ModelBase,
            include_direct_relations=False,
            include_reversed_relations=False
    ) -> Set[str]:
        """
        Find and return all users wich DIRECT related to provided model

        If called from pre_save: for oneToOne and foreigin key will return users from instance, but not from database,
        if you want to get old objects on pre_save - pass the instance obtained from DB instead of the instance from
        signal

        @param include_direct_relations:
        @param include_reversed_relations:
        @type instance: ModelBase Model wich direct related to UserModel via any relation
        @return Set[str]: Unique affected user identities
        """
        assert instance._meta.model != get_user_model(),\
            "Django SSO: get_all_related_users() accepts only direct related models"

        related_users_identities = set()

        for model_attribute_name in dir(instance._meta.model):
            if model_attribute_name[0] == '_':
                continue

            model_attribute = getattr(instance._meta.model, model_attribute_name)

            if include_direct_relations:
                if (
                    (
                        isinstance(model_attribute, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor))
                        and model_attribute.field.related_model == get_user_model()
                    ) or (
                        isinstance(model_attribute, ReverseOneToOneDescriptor)
                        and model_attribute.related.related_model == get_user_model()
                    )
                ):
                    if hasattr(instance, model_attribute_name):
                        object_attribute_value = getattr(instance, model_attribute_name)

                        if object_attribute_value:
                            related_users_identities.add(getattr(object_attribute_value, get_user_model().USERNAME_FIELD))

            if include_reversed_relations:
                if isinstance(model_attribute, ReverseManyToOneDescriptor):
                    if model_attribute.field.model == get_user_model():
                        user_identities = getattr(instance, model_attribute_name).all().values_list(
                            get_user_model().USERNAME_FIELD,
                            flat=True
                        )

                        for user_identy in user_identities:
                            related_users_identities.add(user_identy)

        return related_users_identities

    def _get_users_queryset_by_identities(self, user_identities: Union[List[str], Set[str]]) -> QuerySet:
        return get_user_model().objects.filter(**{
            f'{get_user_model().USERNAME_FIELD}__in': user_identities
        }).all()

    def on_post_delete_user(self, sender: ModelBase, instance: ModelBase, *args, **kwargs):
        self.service_model.cast_event_to_all_services('delete_user', user=instance)

    def on_post_save_user_model(self, sender: ModelBase, instance: ModelBase, *args, **kwargs):
        self.service_model.cast_event_to_all_services('update_account', user=instance)

    def on_pre_save_user_model(self, sender: ModelBase, instance: ModelBase, *args, **kwargs):
        """
        If user identy has changed - emit event about it
        """
        if instance.pk:
            old_identy = get_user_model().objects.filter(id=instance.pk).first()

            if old_identy:
                old_identy = getattr(old_identy, instance.USERNAME_FIELD)

            new_identy = getattr(instance, instance.USERNAME_FIELD)

            if old_identy != new_identy:
                self.service_model.cast_event_to_all_services('change_user_identy', old=old_identy, new=new_identy)
