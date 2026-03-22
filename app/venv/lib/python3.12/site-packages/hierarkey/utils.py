from django.db import router
from django.db.migrations.operations.base import Operation
from django.db.models import Count


class CleanHierarkeyDuplicates(Operation):
    reduces_to_sql = False
    atomic = True
    reversible = True

    def __init__(
        self, model_name, hints=None,
    ):
        self.model_name = model_name
        self.hints = hints or {}

    def deconstruct(self):
        kwargs = {
            "model_name": self.model_name,
        }
        if self.hints:
            kwargs["hints"] = self.hints
        return (self.__class__.__qualname__, [], kwargs)

    def state_forwards(self, app_label, state):
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # CleanHierarkeyDuplicates has access to all models. Ensure that all models are
        # reloaded in case any are delayed.
        from_state.clear_delayed_apps_cache()
        if router.allow_migrate(
            schema_editor.connection.alias, app_label, **self.hints
        ):
            SettingsStoreModel = from_state.apps.get_model(app_label, self.model_name)
            is_global = "object" not in [f.name for f in SettingsStoreModel._meta.fields]

            if is_global:
                qs = SettingsStoreModel.objects.values("key")
            else:
                qs = SettingsStoreModel.objects.values("key", "object")

            for k in qs.annotate(c=Count("*")).filter(c__gt=1):
                if is_global:
                    instance_qs = SettingsStoreModel.objects.filter(key=k["key"])
                else:
                    instance_qs = SettingsStoreModel.objects.filter(key=k["key"], object_id=k["object"])
                all_instances = list(instance_qs)
                # list(qs)[-1] not the same as .last() on postgres, last performs an implicit order by id while
                # list()[-1] orders by page order in the database, which is the behavior we need to match the legacy
                # behavior
                correct_instance = all_instances[-1]
                assert hasattr(correct_instance, "object") == (not is_global)
                instance_qs.exclude(pk=correct_instance.pk).delete()
                # No need to update/clear cache as the resulting value has not changed

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Reverse is a no-op
        pass

    def describe(self):
        return "Cleaning of duplicate hierarkey keys"
