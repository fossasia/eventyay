from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from eventyay.base.models.base import LoggedModel


class SponsorGroup(LoggedModel):
    """
    Represents a group/tier of sponsors (e.g., Platinum, Gold, Silver)
    """
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='sponsor_groups',
        verbose_name=_('Event')
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Group name'),
        help_text=_('e.g., "Platinum Sponsor", "Gold Sponsor"')
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Groups are displayed in ascending order')
    )
    logo_size = models.IntegerField(
        default=120,
        validators=[MinValueValidator(20), MaxValueValidator(500)],
        verbose_name=_('Logo size (px)'),
        help_text=_('Maximum height for partner logos in this group (20-500px)')
    )

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('Sponsor group')
        verbose_name_plural = _('Sponsor groups')
        unique_together = [['event', 'name']]

    def __str__(self):
        return f"{self.event.slug} - {self.name}"


class Partner(LoggedModel):
    """
    Represents a partner/sponsor within a sponsor group
    """
    sponsor_group = models.ForeignKey(
        SponsorGroup,
        on_delete=models.CASCADE,
        related_name='partners',
        verbose_name=_('Sponsor group')
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Partner name')
    )
    link = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Website URL'),
        help_text=_('Optional link to partner website')
    )
    logo = models.ImageField(
        upload_to='partners/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Logo'),
        help_text=_('Partner logo image')
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Partners are displayed in ascending order within their group')
    )

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')

    def __str__(self):
        return self.name

    @property
    def event(self):
        """Convenience property to access the event"""
        return self.sponsor_group.event
