from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField


def partner_logo_upload_to(instance, filename):
    """Generate upload path for partner logos."""
    return f'partner_logos/{instance.group.event.organizer.slug}/{instance.group.event.slug}/{filename}'


class PartnerGroup(models.Model):
    """
    Sponsor/Partner group (e.g., 'Platinum Sponsors', 'Gold Sponsors').
    Groups are displayed in order on the public event landing page.
    """

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='partner_groups',
        verbose_name=_('Event')
    )
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Group name'),
        help_text=_('e.g., "Platinum Sponsors", "Gold Sponsors"')
    )
    position = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Position'),
        help_text=_('Groups are displayed in ascending order')
    )
    logo_size = models.PositiveIntegerField(
        default=160,
        validators=[MinValueValidator(50), MaxValueValidator(500)],
        verbose_name=_('Logo height (pixels)'),
        help_text=_('Logo height in pixels (50-500)')
    )

    class Meta:
        ordering = ['position', 'id']
        verbose_name = _('Partner Group')
        verbose_name_plural = _('Partner Groups')

    def __str__(self):
        return f"{self.event.slug} - {self.name}"


class Partner(models.Model):
    """
    Individual partner/sponsor within a group.
    Each partner has a name, optional link, and optional logo.
    """

    group = models.ForeignKey(
        'PartnerGroup',
        on_delete=models.CASCADE,
        related_name='partners',
        verbose_name=_('Partner Group')
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Partner name')
    )
    link = models.URLField(
        blank=True,
        verbose_name=_('Partner URL'),
        help_text=_('Optional link to partner website')
    )
    logo = models.ImageField(
        upload_to=partner_logo_upload_to,
        blank=True,
        null=True,
        verbose_name=_('Logo'),
        help_text=_('Partner logo image')
    )
    position = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Position'),
        help_text=_('Partners are displayed in ascending order within their group')
    )

    class Meta:
        ordering = ['position', 'id']
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')

    def __str__(self):
        return f"{self.group.name} - {self.name}"
