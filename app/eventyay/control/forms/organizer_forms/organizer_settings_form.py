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
        'organizer_logo_image_large',
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
        'menu_text_scroll_over_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'video_navigation_background_color',
        'video_sidebar_text_color',
        'video_sidebar_hover_color',
        'theme_round_borders',
        'primary_font',
        'privacy_policy',
    ]

    organizer_logo_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'If you provide a logo image, we will by default not show your organization name '
            'in the page header. By default, we show your logo with a size of up to 1140x120 pixels. You '
            'can increase the size with the setting below. We recommend not using small details on the picture '
            'as it will be resized on smaller screens.'
        ),
    )

    def clean(self):
        data = super().clean()
        from eventyay.base.settings import validate_organizer_settings
        validate_organizer_settings(self.obj, data)
        return data

