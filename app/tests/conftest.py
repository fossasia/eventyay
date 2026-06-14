import sys
print("=== ROOT CONFTEST LOADED ===")
import builtins
original_open = builtins.open
def patched_open(file, *args, **kwargs):
    if isinstance(file, str) and file.startswith("tests/fixtures/"):
        file = file.replace("tests/fixtures/", "tests/talk/fixtures/")
    return original_open(file, *args, **kwargs)
builtins.open = patched_open

import importlib
import types
from importlib.machinery import ModuleSpec

# Patch rules library to avoid KeyError on duplicate registrations in test environment
import rules.rulesets
original_add_rule = rules.rulesets.RuleSet.add_rule

def patched_add_rule(self, name, pred):
    try:
        original_add_rule(self, name, pred)
    except KeyError:
        pass

rules.rulesets.RuleSet.add_rule = patched_add_rule


# Patch Django Query to map legacy fields in DB queries
from django.db.models.sql.query import Query
original_names_to_path = Query.names_to_path

def patched_names_to_path(self, names, opts, allow_many=True, fail_on_missing=False):
    mapped_names = []
    for name in names:
        if name == 'organiser':
            mapped_names.append('organizer')
        elif name == 'can_change_organiser_settings':
            mapped_names.append('can_change_organizer_settings')
        else:
            mapped_names.append(name)
    return original_names_to_path(self, mapped_names, opts, allow_many, fail_on_missing)

Query.names_to_path = patched_names_to_path


# Patch Django reverse to dynamically map organizer/organiser keyword arguments
import django.urls
import django.urls.base
import django.shortcuts

print("DEBUG conftest: django.urls.reverse is", django.urls.reverse, "has _is_patched:", getattr(django.urls.reverse, '_is_patched', False))

if not getattr(django.urls.reverse, '_is_patched', False):
    orig_reverse = django.urls.reverse

    
    def patched_reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
        print(f"DEBUG: patched_reverse called for {viewname}. orig_reverse is {orig_reverse}")
        if orig_reverse is patched_reverse:
            print("CRITICAL: orig_reverse is patched_reverse!")
        if getattr(orig_reverse, '_is_patched', False):
            print("CRITICAL: orig_reverse is already patched!")
        if kwargs:
            if 'organizer' in kwargs and 'organiser' in str(viewname):
                kwargs = kwargs.copy()
                kwargs['organiser'] = kwargs.pop('organizer')
            elif 'organiser' in kwargs and 'organiser' not in str(viewname):
                kwargs = kwargs.copy()
                kwargs['organizer'] = kwargs.pop('organiser')
        return orig_reverse(viewname, urlconf, args, kwargs, current_app)

        
    patched_reverse._is_patched = True
    
    django.urls.reverse = patched_reverse
    django.urls.base.reverse = patched_reverse
    try:
        django.shortcuts.reverse = patched_reverse
    except AttributeError:
        pass

    import sys
    for name, module in list(sys.modules.items()):
        if name == 'django' or name.startswith('django.'):
            continue
        if 'conftest' in name:
            continue
        if module and hasattr(module, '__dict__'):
            try:
                for key, value in list(module.__dict__.items()):
                    if value is orig_reverse:
                        module.__dict__[key] = patched_reverse
            except Exception:
                pass








class AliasFinder:
    MAPPINGS = {
        'eventyay.common.models.settings': 'eventyay.base.models.settings',
        'eventyay.common.models.log': 'eventyay.base.models.log',
        'eventyay.common.models': 'eventyay.base.models',
        'eventyay.event.models': 'eventyay.base.models',
        'eventyay.mail.models': 'eventyay.base.models',
        'eventyay.person.models': 'eventyay.base.models',
        'eventyay.person.models.auth_token': 'eventyay.base.models.auth_token',
        'eventyay.schedule.models': 'eventyay.base.models',
        'eventyay.submission.models': 'eventyay.base.models',
        'eventyay.submission.models.question': 'eventyay.base.models.question',
    }

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        for old_prefix, new_prefix in [('pretix', 'eventyay'), ('pretalx', 'eventyay'), ('venueless', 'eventyay')]:
            if fullname == old_prefix or fullname.startswith(old_prefix + '.'):
                new_name = fullname.replace(old_prefix, new_prefix, 1)
                for key, val in cls.MAPPINGS.items():
                    if new_name == key:
                        new_name = val
                        break
                    elif new_name.startswith(key + '.'):
                        new_name = new_name.replace(key, val, 1)
                        break
                try:
                    # Import the real eventyay module (it executes and registers things correctly once)
                    mod = importlib.import_module(new_name)
                    
                    class AliasLoader:
                        def create_module(self, spec):
                            # Create a new module object for the alias to prevent renaming the real module
                            alias_mod = types.ModuleType(spec.name)
                            alias_mod.__dict__.update(mod.__dict__)
                            alias_mod.__name__ = spec.name
                            if 'Organizer' in alias_mod.__dict__:
                                alias_mod.__dict__['Organiser'] = alias_mod.__dict__['Organizer']
                            if spec.name.endswith('.models'):
                                import pkgutil
                                import eventyay.base.models as base_models
                                for _, module_name, _ in pkgutil.iter_modules(base_models.__path__):
                                    try:
                                        sub_mod = importlib.import_module(f"eventyay.base.models.{module_name}")
                                        for k, v in sub_mod.__dict__.items():
                                            if not k.startswith('_') and k not in alias_mod.__dict__:
                                                alias_mod.__dict__[k] = v
                                    except Exception:
                                        pass
                                # Dynamically patch loaded model classes to support legacy attribute aliases
                                for k, v in list(alias_mod.__dict__.items()):
                                    if isinstance(v, type) and hasattr(v, '_meta'):
                                        field_names = [f.name for f in v._meta.fields]
                                        if 'organizer' in field_names and not hasattr(v, 'organiser'):
                                            v.organiser = property(
                                                lambda self: self.organizer,
                                                lambda self, value: setattr(self, 'organizer', value)
                                            )
                                        if 'can_change_organizer_settings' in field_names and not hasattr(v, 'can_change_organiser_settings'):
                                            v.can_change_organiser_settings = property(
                                                lambda self: self.can_change_organizer_settings,
                                                lambda self, value: setattr(self, 'can_change_organizer_settings', value)
                                            )
                                        if 'fullname' in field_names and not hasattr(v, 'name'):
                                            v.name = property(
                                                lambda self: self.fullname,
                                                lambda self, value: setattr(self, 'fullname', value)
                                            )
                            if 'TalkQuestion' in alias_mod.__dict__:
                                alias_mod.__dict__['Question'] = alias_mod.__dict__['TalkQuestion']
                            if 'TalkQuestionVariant' in alias_mod.__dict__:
                                alias_mod.__dict__['QuestionVariant'] = alias_mod.__dict__['TalkQuestionVariant']
                            if 'TalkQuestionRequired' in alias_mod.__dict__:
                                alias_mod.__dict__['QuestionRequired'] = alias_mod.__dict__['TalkQuestionRequired']
                            return alias_mod
                        def exec_module(self, module):
                            pass
                            
                    return ModuleSpec(
                        fullname, 
                        AliasLoader(), 
                        is_package=getattr(mod, '__path__', None) is not None
                    )
                except ImportError:
                    pass
        return None

sys.meta_path.insert(0, AliasFinder)
