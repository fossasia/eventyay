from contextlib import suppress
from pathlib import Path

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from eventyay.common.text.path import path_with_hash
from eventyay.common.urls import get_base_url

from .choices import Choices
from .mixins import PretalxModel


def resource_path(instance, filename):
    base_path = f'{instance.submission.event.slug}/submissions/{instance.submission.code}/resources/'
    return path_with_hash(filename, base_path=base_path)


class ResourceKind(Choices):
    GENERIC = 'generic'
    SLIDES = 'slides'

    valid_choices = [
        (GENERIC, _('Generic resource')),
        (SLIDES, _('Slides')),
    ]


class Resource(PretalxModel):
    """Resources are file uploads belonging to a :class:`~pretalx.submission.models.submission.Submission`."""

    submission = models.ForeignKey(to='Submission', related_name='resources', on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=ResourceKind.get_max_length(),
        choices=ResourceKind.get_choices(),
        default=ResourceKind.GENERIC,
    )
    resource = models.FileField(
        verbose_name=_('File'),
        upload_to=resource_path,
        null=True,
        blank=True,
    )
    link = models.URLField(max_length=400, verbose_name=_('URL'), null=True, blank=True)
    description = models.CharField(null=True, blank=True, max_length=1000, verbose_name=_('Description'))

    objects = ScopedManager(event='submission__event')

    def __str__(self):
        """Help when debugging."""
        return f'Resource(event={self.submission.event.slug}, submission={self.submission.title})'

    @property
    def is_slides(self) -> bool:
        return self.kind == ResourceKind.SLIDES

    @cached_property
    def url(self):
        if self.link:
            return self.link
        with suppress(ValueError):
            url = getattr(self.resource, 'url', None)
            if url:
                base_url = get_base_url(self.submission.event)
                return base_url + url

    @cached_property
    def filename(self):
        with suppress(ValueError):
            if self.resource:
                return Path(self.resource.name).name


def get_slides_resource(submission) -> Resource | None:
    return submission.resources.filter(kind=ResourceKind.SLIDES).order_by('pk').first()


def get_slide_resources(submission):
    return submission.resources.filter(kind=ResourceKind.SLIDES).order_by('pk')


def clear_resource_file(resource: Resource) -> None:
    if resource.resource:
        resource.resource.delete(save=False)


def create_slide_resource(submission, *, link=None, resource_file=None, description=None) -> Resource | None:
    resource = Resource(
        submission=submission,
        kind=ResourceKind.SLIDES,
    )
    resource.kind = ResourceKind.SLIDES
    resource.description = description or _('Slides')

    if link:
        resource.resource = None
        resource.link = link
        resource.save()
        return resource

    if resource_file:
        resource.link = None
        resource.save()
        resource.resource.save(Path(resource_file.name).name, resource_file, save=True)
        return resource

    return None


def delete_slide_resources(submission, resource_ids=None) -> None:
    queryset = get_slide_resources(submission)
    if resource_ids is not None:
        queryset = queryset.filter(pk__in=resource_ids)
    for resource in queryset:
        clear_resource_file(resource)
        resource.delete()


def delete_slide_resource(submission) -> None:
    delete_slide_resources(submission)


def upsert_slide_resource(submission, *, link=None, resource_file=None) -> Resource | None:
    delete_slide_resources(submission)
    return create_slide_resource(submission, link=link, resource_file=resource_file)
