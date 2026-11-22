from django_scopes import scope
from eventyay.celery_app import app
from eventyay.base.models import Event


class EventTask(app.Task):
    def __call__(self, *args, **kwargs):
        if "event_id" in kwargs:
            event_id = kwargs.get("event_id")
            event = event_id if isinstance(event_id, Event) else Event.objects.get(pk=event_id)
            del kwargs["event_id"]
            kwargs["event"] = event
        elif "event" in kwargs:
            event_id = kwargs.get("event")
            event = event_id if isinstance(event_id, Event) else Event.objects.get(pk=event_id)
            kwargs["event"] = event
        else:
            args = list(args)
            event_id = args[0]
            event = event_id if isinstance(event_id, Event) else Event.objects.get(pk=event_id)
            args[0] = event

        with scope(event=event):
            return super().__call__(*args, **kwargs)
