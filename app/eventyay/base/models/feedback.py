from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n
from django_scopes import ScopedManager

from eventyay.common.text.phrases import phrases

from .mixins import PretalxModel


class Feedback(PretalxModel):
    """The Feedback model allows for anonymous feedback by attendees to one or
    all speakers of a.

    :class:`~pretalx.submission.models.submission.Submission`.

    :param speaker: If the ``speaker`` attribute is not set, the feedback is
        assumed to be directed to all speakers.
    """

    # Maps integer rating values to (emoji, translated label) tuples.
    # Order: 5 (best) → 1 (worst) matching the left-to-right display order.
    EMOJI_RATING_MAP = {
        5: ('😍', _('Excellent')),
        4: ('🙂', _('Good')),
        3: ('😐', _('Okay')),
        2: ('🙁', _('Bad')),
        1: ('😡', _('Terrible')),
    }

    talk = models.ForeignKey(
        to='Submission',
        related_name='feedback',
        on_delete=models.PROTECT,
        verbose_name=_n('Session', 'Sessions', 1),
    )
    speaker = models.ForeignKey(
        to='User',
        related_name='feedback',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_n('Speaker', 'Speakers', 1),
    )
    rating = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    review = models.TextField(verbose_name=_('Feedback'), help_text=phrases.base.use_markdown)
    
    author = models.ForeignKey(
        to='User',
        related_name='submitted_feedbacks',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Author'),
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Is public'),
        help_text=_('If disabled, the feedback is anonymous to the speaker and not shown publicly.')
    )
    is_reported = models.BooleanField(
        default=False,
        verbose_name=_('Is reported'),
        help_text=_('Indicates whether this feedback has been reported by a user.')
    )
    report_count = models.IntegerField(
        default=0,
        verbose_name=_('Report count'),
        help_text=_('Number of times this feedback has been reported.')
    )
    status = models.CharField(
        max_length=20,
        default='published',
        choices=(
            ('published', _('Published')),
            ('pending', _('Pending Review')),
            ('hidden', _('Hidden')),
            ('deleted', _('Deleted')),
        ),
        verbose_name=_('Status'),
    )
    parent = models.ForeignKey(
        to='self',
        related_name='replies',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_('Parent feedback'),
    )

    objects = ScopedManager(event='talk__event')

    @property
    def rating_emoji(self) -> str:
        if self.rating and self.rating in self.EMOJI_RATING_MAP:
            return self.EMOJI_RATING_MAP[self.rating][0]
        return ''

    @property
    def rating_label(self) -> str:
        if self.rating and self.rating in self.EMOJI_RATING_MAP:
            return str(self.EMOJI_RATING_MAP[self.rating][1])
        return ''

    def clean(self):
        super().clean()
        if self.parent:
            self.rating = None
        elif self.rating is not None and self.rating not in self.EMOJI_RATING_MAP:
            raise ValidationError({'rating': _('Rating must be between 1 and 5.')})

    def save(self, *args, **kwargs):
        if self.parent:
            self.rating = None
        super().save(*args, **kwargs)

    def __str__(self):
        """Help when debugging."""
        return f'Feedback(event={self.talk.event.slug}, talk={self.talk.title}, rating={self.rating}, status={self.status})'

class FeedbackReaction(PretalxModel):
    feedback = models.ForeignKey(
        to='Feedback',
        related_name='reactions',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        to='User',
        related_name='feedback_reactions',
        on_delete=models.CASCADE,
    )
    is_upvote = models.BooleanField(default=True)

    class Meta:
        unique_together = (('feedback', 'user'),)

    objects = ScopedManager(event='feedback__talk__event')
