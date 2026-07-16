from django.utils.translation import gettext_lazy as _

from eventyay.base.models import OrderPosition
from eventyay.base.ticketoutput import BaseTicketOutput


class BadgeOutputProvider(BaseTicketOutput):
    identifier = 'badge'
    verbose_name = _('Badge output')
    download_button_text = _('Download Badge')
    multi_download_enabled = True

    def generate(self, op: OrderPosition) -> tuple[str, str, bytes]:
        try:
            from .exporters import OPTIONS, render_pdf

            pdf_buffer = render_pdf(op.order.event, [op], OPTIONS['one'])
            if pdf_buffer is None:
                raise Exception('Failed to generate PDF')

            if hasattr(pdf_buffer, 'getvalue'):
                pdf_content = pdf_buffer.getvalue()
            else:
                pdf_content = pdf_buffer

            return 'badge.pdf', 'application/pdf', pdf_content

        except Exception as e:
            raise e

    def generate_order(self, order) -> tuple[str, str, bytes]:
        try:
            from .exporters import OPTIONS, render_pdf

            positions = list(
                order.positions.select_related('product', 'variation', 'addon_to', 'subevent', 'seat').prefetch_related(
                    'answers', 'answers__question', 'answers__options'
                )
            )

            # Filter positions that should generate tickets
            valid_positions = [op for op in positions if op.generate_ticket]

            if not valid_positions:
                raise Exception('No badges to generate')

            pdf_buffer = render_pdf(order.event, valid_positions, OPTIONS['one'])
            if pdf_buffer is None:
                raise Exception('Failed to generate PDF')

            if hasattr(pdf_buffer, 'getvalue'):
                pdf_content = pdf_buffer.getvalue()
            else:
                pdf_content = pdf_buffer

            return f'badges_{order.code}.pdf', 'application/pdf', pdf_content

        except Exception as e:
            raise e

    @property
    def settings_form_fields(self):
        return super().settings_form_fields

    def settings_content_render(self, request):
        from django.template.loader import get_template

        template = get_template('pretixplugins/badges/form.html')
        return template.render({'request': request})
