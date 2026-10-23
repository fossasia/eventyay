from django_scopes import scope


def classscope(attr='o', event_attr=None):
    def wrap(fn):
        def wrapped(self, *args, **kwargs):
            if event_attr and getattr(self, event_attr, None):
                with scope(organizer=getattr(self, attr)), scope(event=getattr(self, event_attr)):
                    return fn(self, *args, **kwargs)
            with scope(organizer=getattr(self, attr)):
                return fn(self, *args, **kwargs)

        return wrapped

    return wrap
