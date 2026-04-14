from rest_framework import exceptions

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.mail.context import get_invalid_placeholders
from eventyay.base.models.mail import MailTemplate, MailTemplateRoles


@register_serializer(versions=CURRENT_VERSIONS)
class MailTemplateSerializer(PretalxSerializer):
    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "role",
            "subject",
            "text",
            "reply_to",
            "bcc",
        )

    def create(self, validated_data):
        validated_data["event"] = self.event
        return super().create(validated_data)

    def _validate_text(self, value):
        # Build a MailTemplate with the correct role so valid_placeholders
        # returns only the placeholders available in that role's mail context.
        # Without this, creating a NEW_SCHEDULE template via API would accept
        # submission-level placeholders (like {submission_title}) that aren't
        # available at send time, causing KeyError crashes.
        role = self.initial_data.get("role", getattr(self.instance, "role", None))
        # Only use the role for placeholder scoping if it's a known value;
        # invalid roles are rejected by DRF's own field validation separately.
        valid_roles = {choice.value for choice in MailTemplateRoles}
        if role not in valid_roles:
            role = None
        if not self.instance:
            kwargs = {"event": self.event}
            if role:
                kwargs["role"] = role
            valid_placeholders = MailTemplate(**kwargs).valid_placeholders
        else:
            template = self.instance
            if role and role != template.role:
                template = MailTemplate(event=self.event, role=role)
            valid_placeholders = template.valid_placeholders
        try:
            fields = get_invalid_placeholders(value, valid_placeholders)
        except Exception:
            raise exceptions.ValidationError(
                "Invalid email template! "
                "Please check that you don’t have stray { or } somewhere, "
                "and that there are no spaces inside the {} blocks."
            )
        if fields:
            fields = ", ".join("{" + field + "}" for field in fields)
            raise exceptions.ValidationError(f"Unknown placeholder! {fields}")
        return value

    def validate_subject(self, value):
        return self._validate_text(value)

    def validate_text(self, value):
        return self._validate_text(value)
