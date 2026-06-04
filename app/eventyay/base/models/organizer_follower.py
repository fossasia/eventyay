from django.db import models
from django.utils.translation import gettext_lazy as _


class OrganizerFollower(models.Model):
    """
    Records that a user is following an organizer's community profile.

    Followers receive email notifications when the organizer publishes a new
    public event (if the organizer has follow-based notifications enabled and
    the user has not opted out).

    """

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='followed_organizers',
        verbose_name=_('User'),
    )
    organizer = models.ForeignKey(
        'Organizer',
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name=_('Organizer'),
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organizer')
        verbose_name = _('Organizer follower')
        verbose_name_plural = _('Organizer followers')
        ordering = ('-created',)

    def __str__(self) -> str:
        return f'{self.user} → {self.organizer}'
