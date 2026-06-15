from django.conf import settings
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm
from eventyay.consts import SizeKey
from eventyay.control.forms import ExtFileField


class OrganizerSettingsForm(SettingsForm):
    auto_fields = [
        'contact_mail',
        'imprint_url',
        'organizer_info_text',
        'event_list_type',
        'event_list_availability',
        'organizer_homepage_text',
        'organizer_link_back',
        'organizer_header_image_large',
        'community_follow_enabled',
        'community_show_follower_count',
        'giftcard_length',
        'giftcard_expiry_years',
        'locales',
        'region',
        'event_team_provisioning',
        'primary_color',
        'header_background_color',
        'header_text_color',
        'navigation_text_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'privacy_policy',
    ]

    organizer_logo_image = ExtFileField(
        label=_('Logo'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'Upload your organizer logo. Accepted formats: PNG, JPEG, GIF. '
            'The logo is displayed in the page header.'
        ),
    )

    organizer_header_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'This image appears at the top of all organizer pages, replacing the default color or pattern. '
            'We recommend an image 1140 px wide and 120 px in height.'
        ),
    )

