"""Shared helpers for serializing public submission resources in agenda exports."""

from eventyay.common.utils.language import localize_event_text


def iter_public_resources(submission, event):
    for resource in submission.resources.all():
        if event.cfp.is_resource_public(resource):
            yield resource


def public_resource_links(submission, event):
    return [
        {'title': localize_event_text(resource.description), 'url': resource.link}
        for resource in iter_public_resources(submission, event)
        if resource.link
    ]


def public_resource_attachments(submission, event):
    return [
        {'title': localize_event_text(resource.description), 'url': resource.url}
        for resource in iter_public_resources(submission, event)
        if not resource.link and resource.url
    ]


def frab_public_resource_links(submission, event):
    return [{**entry, 'type': 'related'} for entry in public_resource_links(submission, event)]


def frab_public_resource_attachments(submission, event):
    return [{**entry, 'type': 'related'} for entry in public_resource_attachments(submission, event)]


def enriched_resource_entry(resource):
    return {
        'resource': resource.url,
        'description': str(resource.description),
        'link': resource.link,
    }
