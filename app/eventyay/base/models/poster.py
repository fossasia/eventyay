from contextlib import suppress
import uuid

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay.common.text.path import path_with_hash


def default_text():
    return []


def poster_file_path(instance, filename: str) -> str:
    event_slug = getattr(instance.event, "slug", str(instance.event_id))
    base_path = f"events/{event_slug}/posters"
    return path_with_hash(filename, base_path=base_path)


def poster_preview_file_path(instance, filename: str) -> str:
    event_slug = getattr(instance.event, "slug", str(instance.event_id))
    base_path = f"events/{event_slug}/posters/previews"
    return path_with_hash(filename, base_path=base_path)


class Poster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    import_id = models.TextField(null=True, blank=True, db_index=True)
    title = models.TextField(null=True)
    abstract = models.JSONField(default=default_text)
    authors = models.JSONField(default=default_text)
    tags = models.JSONField(default=default_text)
    category = models.TextField(null=True, blank=True)

    poster_url = models.URLField(null=True, blank=True, max_length=2048, verbose_name=_("Poster URL"))
    poster_preview = models.URLField(null=True, blank=True, max_length=2048, verbose_name=_("Poster Preview URL"))
    poster_file = models.FileField(
        upload_to=poster_file_path,
        null=True,
        blank=True,
        max_length=255,
        verbose_name=_("Poster File"),
    )
    poster_preview_file = models.FileField(
        upload_to=poster_preview_file_path,
        null=True,
        blank=True,
        max_length=255,
        verbose_name=_("Poster Preview File"),
    )
    schedule_session = models.TextField(null=True, blank=True)

    event = models.ForeignKey(
        to="Event",
        related_name="posters",
        on_delete=models.CASCADE,
    )
    parent_room = models.ForeignKey(
        to="Room",
        related_name="child_posters",
        on_delete=models.CASCADE,
    )
    presentation_room = models.ForeignKey(
        to="Room",
        related_name="presentation_posters",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    channel = models.ForeignKey(
        to="Channel",
        related_name="posters",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    @cached_property
    def resolved_poster_url(self):
        if self.poster_file:
            with suppress(ValueError):
                return self.poster_file.url
        return self.poster_url

    @cached_property
    def resolved_poster_preview(self):
        if self.poster_preview_file:
            with suppress(ValueError):
                return self.poster_preview_file.url
        return self.poster_preview

    def serialize(self, user=None, list_format=False):
        abstract = self.abstract
        if list_format and abstract and "ops" in abstract:
            max_abstract_length = 1000
            shortened_abstract = {"ops": []}
            char_count = 0
            for op in self.abstract["ops"]:
                if not isinstance(op.get("insert"), str):
                    continue

                if len(op["insert"]) > max_abstract_length - char_count:
                    op["insert"] = (
                        op["insert"][: (max_abstract_length - char_count)] + "…"
                    )
                shortened_abstract["ops"].append(op)

                char_count += len(op["insert"])
                if char_count >= max_abstract_length:
                    break

            abstract = shortened_abstract

        result = dict(
            id=str(self.id),
            title=self.title,
            abstract=abstract,
            authors=self.authors,
            category=self.category,
            tags=self.tags,
            poster_url=self.resolved_poster_url,
            poster_preview=self.resolved_poster_preview,
        )

        if not list_format:
            votes = self.votes.all().count()
            presenters = []
            for presenter in self.presenters.order_by("id").all():
                presenters.append(
                    presenter.user.serialize_public(
                        trait_badges_map=self.event.config.get("trait_badges_map")
                    )
                )
            links = list(
                self.links.order_by("display_text").values(
                    "display_text", "url", "sorting_priority"
                )
            )
            result["links"] = links
            result["presenters"] = presenters
            result["channel"] = (
                str(self.channel_id) if getattr(self, "channel_id", None) else None
            )
            result["votes"] = votes
            result["presentation_room_id"] = (
                str(self.presentation_room_id)
                if getattr(self, "presentation_room_id", None)
                else None
            )
            result["schedule_session"] = self.schedule_session
            result["parent_room_id"] = str(self.parent_room_id)

        if user:
            result["has_voted"] = self.votes.filter(user=user).exists()
        return result

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.parent_room.touch()
        return r

    def delete(self, *args, **kwargs):
        if self.poster_file:
            with suppress(ValueError, OSError):
                self.poster_file.delete(save=False)
        if self.poster_preview_file:
            with suppress(ValueError, OSError):
                self.poster_preview_file.delete(save=False)
        r = super().delete(*args, **kwargs)
        self.parent_room.touch()
        return r


class PosterPresenter(models.Model):
    poster = models.ForeignKey(
        to=Poster,
        db_index=True,
        related_name="presenters",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="poster_presenter",
    )

    class Meta:
        unique_together = (("user", "poster"),)

    def save(self, *args, **kwargs):
        r = super().save(*args, **kwargs)
        self.user.touch()
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        self.user.touch()
        return r


class PosterVote(models.Model):
    poster = models.ForeignKey(
        to="Poster", related_name="votes", on_delete=models.CASCADE
    )
    datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        to="user", related_name="poster_votes", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (("user", "poster"),)


class PosterLink(models.Model):
    poster = models.ForeignKey(
        to=Poster,
        db_index=True,
        related_name="links",
        on_delete=models.CASCADE,
    )
    display_text = models.CharField(max_length=300, blank=False)
    url = models.URLField(blank=False)
    sorting_priority = models.IntegerField(default=0)
