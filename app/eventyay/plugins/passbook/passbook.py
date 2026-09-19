import logging
import os
import re
import tempfile
from collections import OrderedDict
from zoneinfo import ZoneInfo

from django import forms
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.validators import RegexValidator
from django.utils.formats import date_format
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from wallet.models import Barcode, BarcodeFormat, EventTicket, Location, Pass

from eventyay.base.models import OrderPosition
from eventyay.base.ticketoutput import BaseTicketOutput
from eventyay.control.forms import ClearableBasenameFileInput
from eventyay.multidomain.urlreverse import build_absolute_uri

from .forms import PNGImageField


logger = logging.getLogger(__name__)


class PassbookOutput(BaseTicketOutput):
    identifier = 'passbook'
    verbose_name = _('Passbook Tickets')
    download_button_icon = 'fa-mobile'
    download_button_text = _('Wallet/Passbook')
    multi_download_enabled = False

    @property
    def preview_allowed(self) -> bool:
        return bool(self.event.settings.get('passbook_certificate_file') and self.event.settings.get('passbook_key'))

    @property
    def settings_form_fields(self) -> dict:
        return OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    'selfscale',
                    forms.BooleanField(
                        label=_('I would like to scale the graphics myself'),
                        help_text=_(
                            'In some instances, the downscaling of graphics done by the Wallet-app is not '
                            'satisfactory. By checking this box, you can provide prescaled files in the correct '
                            'dimensions.'
                            '<br><br>'
                            'If you choose to do so, please only upload your pictures in the regular display size '
                            'and not the increased retina size.'
                        ),
                        required=False,
                    ),
                ),
                (
                    'icon',
                    PNGImageField(
                        label=_('Event icon'),
                        help_text='{} {}'.format(
                            _('Display size is {} x {} pixels.').format(29, 29),
                            _('We suggest an upload size of {} x {} pixels to support retina displays.').format(87, 87),
                        ),
                        required=False,
                    ),
                ),
                (
                    'icon2x',
                    PNGImageField(
                        label=_('Event icon for Retina {}x displays').format(2),
                        help_text=_('Display size is {} x {} pixels.').format(58, 58),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'icon3x',
                    PNGImageField(
                        label=_('Event icon for Retina {}x displays').format(3),
                        help_text=_('Display size is {} x {} pixels.').format(87, 87),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'logo',
                    PNGImageField(
                        label=_('Event logo'),
                        help_text='{} {}'.format(
                            _('Display size is {} x {} pixels.').format(160, 50),
                            _('We suggest an upload size of {} x {} pixels to support retina displays.').format(
                                480, 150
                            ),
                        ),
                        required=False,
                    ),
                ),
                (
                    'logo2x',
                    PNGImageField(
                        label=_('Event logo for Retina {}x displays').format(2),
                        help_text=_('Display size is {} x {} pixels.').format(320, 100),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'logo3x',
                    PNGImageField(
                        label=_('Event logo for Retina {}x displays').format(3),
                        help_text=_('Display size is {} x {} pixels.').format(480, 150),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'background',
                    PNGImageField(
                        label=_('Pass background image'),
                        help_text='{} {}'.format(
                            _('Display size is {} x {} pixels.').format(180, 220),
                            _(
                                'We suggest an upload size of {} x {} pixels to support retina displays. '
                                'Please note: iOS Wallet seems to ignore custom text color and uses white text '
                                'if a background image is used. Please use a dark background '
                                'image to provide sufficient text contrast.'
                            ).format(540, 660),
                        ),
                        required=False,
                    ),
                ),
                (
                    'background2x',
                    PNGImageField(
                        label=_('Pass background image for Retina {}x displays').format(2),
                        help_text=_('Display size is {} x {} pixels.').format(360, 440),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'background3x',
                    PNGImageField(
                        label=_('Pass background image for Retina {}x displays').format(3),
                        help_text=_('Display size is {} x {} pixels.').format(540, 660),
                        widget=ClearableBasenameFileInput(
                            attrs={
                                'data-display-dependency': '#id_ticketoutput_passbook_selfscale',
                            }
                        ),
                        required=False,
                    ),
                ),
                (
                    'bg_color',
                    forms.CharField(
                        label=_('Background color'),
                        help_text=_('If you use a background image, the background color will have no effect.'),
                        validators=[
                            RegexValidator(
                                regex='^#[0-9a-fA-F]{6}$',
                                message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                            ),
                        ],
                        required=False,
                        widget=forms.TextInput(
                            attrs={
                                'class': 'colorpickerfield no-contrast',
                                'placeholder': '#RRGGBB',
                            }
                        ),
                    ),
                ),
                (
                    'fg_color',
                    forms.CharField(
                        label=_('Text color'),
                        help_text=_('If you use a background image, iOS Wallet ignores the custom text color.'),
                        validators=[
                            RegexValidator(
                                regex='^#[0-9a-fA-F]{6}$',
                                message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                            ),
                        ],
                        required=False,
                        widget=forms.TextInput(
                            attrs={
                                'class': 'colorpickerfield no-contrast',
                                'placeholder': '#RRGGBB',
                            }
                        ),
                    ),
                ),
                (
                    'label_color',
                    forms.CharField(
                        label=_('Label color'),
                        validators=[
                            RegexValidator(
                                regex='^#[0-9a-fA-F]{6}$',
                                message=_('Please enter the hexadecimal code of a color, e.g. #990000.'),
                            ),
                        ],
                        required=False,
                        widget=forms.TextInput(
                            attrs={
                                'class': 'colorpickerfield no-contrast',
                                'placeholder': '#RRGGBB',
                            }
                        ),
                    ),
                ),
                (
                    'latitude',
                    forms.FloatField(
                        label=_('Event location (latitude)'),
                        help_text=_('Will be taken from event settings by default.'),
                        required=False,
                    ),
                ),
                (
                    'longitude',
                    forms.FloatField(
                        label=_('Event location (longitude)'),
                        help_text=_('Will be taken from event settings by default.'),
                        required=False,
                    ),
                ),
            ]
        )

    def generate_pass(self, order_position: OrderPosition):
        order = order_position.order
        ev = order_position.subevent or order.event
        raw_tz = getattr(order.event, 'timezone', 'UTC')
        if isinstance(raw_tz, str):
            try:
                tz = ZoneInfo(raw_tz)
            except Exception:
                tz = ZoneInfo('UTC')
        elif raw_tz:
            tz = raw_tz
        else:
            tz = ZoneInfo('UTC')

        card = EventTicket()

        logo_file = self.event.settings.get('ticketoutput_passbook_logo')
        if logo_file:
            logo_text = None

            if order.event.has_subevents or ev.date_admission:
                if ev.date_admission:
                    card.addHeaderField(
                        'doorsAdmissionHeader',
                        date_format(ev.date_admission.astimezone(tz), 'SHORT_DATETIME_FORMAT'),
                        gettext('Admission time'),
                    )
                else:
                    card.addHeaderField(
                        'doorsAdmissionHeader',
                        ev.get_date_from_display(tz, short=True),
                        gettext('Begin'),
                    )
        else:
            logo_text = str(ev.name)
            if order.event.has_subevents:
                logo_text += f' ({ev.get_date_from_display(tz, short=True)})'

        # Ticket content
        card.addPrimaryField('eventName', str(ev.name), gettext('Event'))

        product = getattr(order_position, 'product', None) or getattr(order_position, 'item', None)
        ticket = str(product.name) if product else ''
        if order_position.variation:
            ticket += ' - ' + str(order_position.variation)

        card.addSecondaryField('ticket', ticket, gettext('Product'))

        if ev.seating_plan_id is not None:
            if order_position.seat:
                card.addAuxiliaryField('seat', str(order_position.seat), gettext('Seat'))
            else:
                card.addAuxiliaryField('seat', gettext('General admission'), gettext('Seat'))
        elif order_position.attendee_name:
            card.addAuxiliaryField('name', order_position.attendee_name, gettext('Attendee name'))

        if ev.date_admission:
            card.addBackField(
                'doorsAdmission',
                date_format(ev.date_admission.astimezone(tz), 'SHORT_DATETIME_FORMAT'),
                gettext('Admission time'),
            )

        valid_from = getattr(order_position, 'valid_from', None)
        valid_until = getattr(order_position, 'valid_until', None)

        if valid_from:
            card.addAuxiliaryField(
                'doorsOpen',
                date_format(valid_from.astimezone(tz), 'SHORT_DATETIME_FORMAT'),
                gettext('From'),
            )
        elif ev.date_from:
            card.addAuxiliaryField('doorsOpen', ev.get_date_from_display(tz, short=True), gettext('From'))

        if valid_until:
            if ev.seating_plan_id:
                card.addBackField(
                    'doorsClose',
                    date_format(
                        valid_until.astimezone(tz),
                        'SHORT_DATETIME_FORMAT',
                    ),
                    gettext('To'),
                )
            else:
                card.addAuxiliaryField(
                    'doorsClose',
                    date_format(
                        valid_until.astimezone(tz),
                        'SHORT_DATETIME_FORMAT',
                    ),
                    gettext('To'),
                )
        elif order.event.settings.show_date_to and ev.date_to:
            if ev.seating_plan_id:
                card.addBackField('doorsClose', ev.get_date_to_display(tz, short=True), gettext('To'))
            else:
                card.addAuxiliaryField('doorsClose', ev.get_date_to_display(tz, short=True), gettext('To'))

        if order_position.attendee_name:
            card.addBackField('name', order_position.attendee_name, gettext('Attendee name'))

        if order.email:
            card.addBackField('email', order.email, gettext('Ordered by'))
        card.addBackField('organizer', str(order.event.organizer), gettext('Organizer'))
        if order.event.settings.contact_mail:
            card.addBackField(
                'organizerContact',
                order.event.settings.contact_mail,
                gettext('Organizer contact'),
            )
        card.addBackField('orderCode', order.code, gettext('Order code'))
        card.addBackField(
            'purchaseDate',
            date_format(order.datetime.astimezone(tz), 'SHORT_DATETIME_FORMAT'),
            gettext('Purchase date'),
        )

        if order_position.subevent:
            card.addBackField(
                'website',
                build_absolute_uri(
                    order.event,
                    'presale:event.index',
                    {'subevent': order_position.subevent.pk},
                ),
                gettext('Website'),
            )
        else:
            card.addBackField(
                'website',
                build_absolute_uri(order.event, 'presale:event.index'),
                gettext('Website'),
            )

        try:
            if hasattr(product, 'meta_data'):
                backfieldprop = product.meta_data.get('eventyay_passbook_backfield') or product.meta_data.get(
                    'pretix_passbook_backfield'
                )
                if backfieldprop:
                    card.addBackField(
                        'metabackfield',
                        backfieldprop,
                        gettext('Additional information'),
                    )
        except Exception:
            pass

        passfile = Pass(
            card,
            passTypeIdentifier=order.event.settings.passbook_pass_type_id or '',
            organizationName=str(ev.name),
            teamIdentifier=order.event.settings.passbook_team_id or '',
        )

        passfile.serialNumber = f'{order.event.organizer.slug}-{order.event.slug}-{order.code}-{order_position.pk}'

        passfile.description = gettext('Ticket for {event} ({product})').format(event=ev.name, product=ticket)
        passfile.barcode = Barcode(message=order_position.secret, format=BarcodeFormat.QR)
        passfile.barcode.altText = order_position.secret

        date_from_local_time = ev.date_from.astimezone(tz)
        date_to_local_time = ev.date_to.astimezone(tz) if ev.date_to else None

        if valid_until and valid_from and valid_from.astimezone(tz).date() != valid_until.astimezone(tz).date():
            passfile.exprirationDate = valid_until.astimezone(tz).isoformat()
        elif valid_from:
            passfile.relevantDate = valid_from.astimezone(tz).isoformat()
            if valid_until:
                passfile.exprirationDate = valid_until.astimezone(tz).isoformat()
        elif (
            order.event.settings.show_date_to
            and date_to_local_time
            and date_to_local_time.date() != date_from_local_time.date()
        ):
            passfile.exprirationDate = date_to_local_time.isoformat()
        elif date_from_local_time:
            passfile.relevantDate = date_from_local_time.isoformat()

        lat = self.event.settings.get('ticketoutput_passbook_latitude') or self.event.settings.get('passbook_latitude')
        lon = self.event.settings.get('ticketoutput_passbook_longitude') or self.event.settings.get(
            'passbook_longitude'
        )

        if lat and lon:
            passfile.locations = [Location(float(lat), float(lon))]
        elif order_position.subevent and order_position.subevent.geo_lat and order_position.subevent.geo_lon:
            passfile.locations = [Location(order_position.subevent.geo_lat, order_position.subevent.geo_lon)]
        elif self.event.geo_lat and self.event.geo_lon:
            passfile.locations = [Location(self.event.geo_lat, self.event.geo_lon)]

        icon_file = self.event.settings.get('ticketoutput_passbook_icon')
        if icon_file:
            passfile.addFile('icon.png', default_storage.open(icon_file.name, 'rb'))
        else:
            default_icon = finders.find('eventyay_passbook/icon.png')
            if not default_icon:
                default_icon = os.path.join(os.path.dirname(__file__), 'static', 'eventyay_passbook', 'icon.png')
            if default_icon and os.path.exists(default_icon):
                passfile.addFile('icon.png', open(default_icon, 'rb'))

        if logo_file:
            passfile.addFile('logo.png', default_storage.open(logo_file.name, 'rb'))
        else:
            default_logo = finders.find('eventyay_passbook/logo.png')
            if not default_logo:
                default_logo = os.path.join(os.path.dirname(__file__), 'static', 'eventyay_passbook', 'logo.png')
            if default_logo and os.path.exists(default_logo):
                passfile.addFile('logo.png', open(default_logo, 'rb'))
        passfile.logoText = logo_text

        bg_file = self.event.settings.get('ticketoutput_passbook_background')
        if bg_file:
            passfile.addFile('background.png', default_storage.open(bg_file.name, 'rb'))

        if self.event.settings.get('ticketoutput_passbook_selfscale'):
            icon2x_file = self.event.settings.get('ticketoutput_passbook_icon2x')
            if icon2x_file:
                passfile.addFile('icon@2x.png', default_storage.open(icon2x_file.name, 'rb'))

            icon3x_file = self.event.settings.get('ticketoutput_passbook_icon3x')
            if icon3x_file:
                passfile.addFile('icon@3x.png', default_storage.open(icon3x_file.name, 'rb'))

            logo2x_file = self.event.settings.get('ticketoutput_passbook_logo2x')
            if logo2x_file:
                passfile.addFile('logo@2x.png', default_storage.open(logo2x_file.name, 'rb'))

            logo3x_file = self.event.settings.get('ticketoutput_passbook_logo3x')
            if logo3x_file:
                passfile.addFile('logo@3x.png', default_storage.open(logo3x_file.name, 'rb'))

            bg2x_file = self.event.settings.get('ticketoutput_passbook_background2x')
            if bg2x_file:
                passfile.addFile('background2x.png', default_storage.open(bg2x_file.name, 'rb'))

            bg3x_file = self.event.settings.get('ticketoutput_passbook_background3x')
            if bg3x_file:
                passfile.addFile('background@3x.png', default_storage.open(bg3x_file.name, 'rb'))

        try:
            if hasattr(product, 'meta_data'):
                thumbnailprop = product.meta_data.get('eventyay_passbook_thumbnail') or product.meta_data.get(
                    'pretix_passbook_thumbnail'
                )
                if thumbnailprop and re.match(r'(\d+/)?pub/', thumbnailprop):
                    passfile.addFile('thumbnail.png', default_storage.open(thumbnailprop, 'rb'))
        except Exception:
            pass

        bg_color = self.event.settings.get('ticketoutput_passbook_bg_color')
        fg_color = self.event.settings.get('ticketoutput_passbook_fg_color')
        label_color = self.event.settings.get('ticketoutput_passbook_label_color')
        if bg_color:
            passfile.backgroundColor = bg_color
        if fg_color:
            passfile.foregroundColor = fg_color
        if label_color:
            passfile.labelColor = label_color
        return passfile

    def generate(self, order_position: OrderPosition) -> tuple[str, str, bytes]:
        order = order_position.order

        cert_file = order.event.settings.get('passbook_certificate_file', as_type=File, binary_file=True)
        ca_file = order.event.settings.get('passbook_wwdr_certificate_file', as_type=File, binary_file=True)
        key_content = order.event.settings.get('passbook_key')

        if not cert_file or not key_content:
            raise ValidationError(gettext('Passbook certificates are not configured.'))

        passfile = self.generate_pass(order_position)
        filename = f'{order.event.slug}-{order.code}.pkpass'

        with (
            tempfile.NamedTemporaryFile('w', encoding='utf-8') as keyfile,
            tempfile.NamedTemporaryFile('wb') as certfile,
            tempfile.NamedTemporaryFile('wb') as cafile,
        ):
            certfile.write(cert_file.read())
            certfile.flush()

            if ca_file:
                cafile.write(ca_file.read())
            cafile.flush()

            keyfile.write(key_content)
            keyfile.flush()
            _pass = passfile.create(
                certfile.name,
                keyfile.name,
                cafile.name,
                order.event.settings.get('passbook_key_password', ''),
            )

        _pass.seek(0)
        return filename, 'application/vnd.apple.pkpass', _pass.read()
