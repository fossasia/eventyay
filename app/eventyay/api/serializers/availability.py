from datetime import UTC

from django.db import transaction
from rest_framework.serializers import BooleanField, ModelSerializer, ValidationError

from eventyay.base.models.availability import Availability


class AvailabilitySerializer(ModelSerializer):
    allDay = BooleanField(
        help_text="Computed field indicating if an availability fills an entire day.",
        read_only=True,
        source="all_day",
    )

    class Meta:
        model = Availability
        fields = ("start", "end", "allDay")

    def validate(self, data):
        """Saving replaces all existing availabilities, so a broken one has to be rejected here."""
        missing = {field: 'This field is required.' for field in ('start', 'end') if not data.get(field)}
        if missing:
            raise ValidationError(missing)
        # In UTC, so the repeated hour when clocks go back is ordered correctly.
        if data['end'].astimezone(UTC) <= data['start'].astimezone(UTC):
            raise ValidationError({'end': 'The end of an availability must be after its start.'})
        return data


class AvailabilitiesMixin:

    def _handle_availabilities(self, instance, availabilities_data, field):
        availabilities = []
        for avail_data in availabilities_data:
            avail = Availability(
                event=self.event,
                start=avail_data["start"],
                end=avail_data["end"],
            )
            availabilities.append(avail)

        merged_availabilities = Availability.union(availabilities)
        for avail in merged_availabilities:
            setattr(avail, field, instance)

        with transaction.atomic():
            instance.availabilities.all().delete()
            Availability.objects.bulk_create(merged_availabilities)
