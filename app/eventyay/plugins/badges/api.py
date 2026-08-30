import base64

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.api.serializers.order import CompatibleJSONField
from eventyay.base.models import OrderPosition
from eventyay.base.services.tickets import generate

from .apps import PDFRenderer
from .exporters import _open_layout_background
from .models import BadgeLayout, BadgeProduct


class BadgeProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = BadgeProduct
        fields = ('id', 'product', 'layout')


class NestedProductAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = BadgeProduct
        fields = ('product',)


class BadgeLayoutSerializer(I18nAwareModelSerializer):
    layout = CompatibleJSONField()
    ask_user_fields = CompatibleJSONField()
    product_assignments = NestedProductAssignmentSerializer(many=True)
    size = CompatibleJSONField()

    class Meta:
        model = BadgeLayout
        fields = (
            'id',
            'name',
            'default',
            'allow_customization',
            'allow_badge_editing',
            'layout',
            'ask_user_fields',
            'size',
            'background',
            'product_assignments',
        )


class BadgeLayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeLayoutSerializer
    queryset = BadgeLayout.objects.none()
    lookup_field = 'id'
    permission = 'can_view_orders'

    def get_queryset(self):
        return self.request.event.badge_layouts.all()

    @action(detail=True, methods=['get'])
    def background(self, request, **kwargs):
        """Return the PDF the server uses as this layout's badge background."""
        layout = self.get_object()
        try:
            background_file = _open_layout_background(layout)
        except (OSError, TypeError, ValueError):
            return Response({'detail': 'No badge background is available.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            pdf_bytes = background_file.read()
        finally:
            background_file.close()
        if not pdf_bytes:
            return Response({'detail': 'No badge background is available.'}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="badge-background-{layout.pk}.pdf"'
        return response


class BadgeProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeProductAssignmentSerializer
    queryset = BadgeProduct.objects.none()
    lookup_field = 'id'
    permission = 'can_view_orders'

    def get_queryset(self):
        return BadgeProduct.objects.filter(product__event=self.request.event)


class BadgePreviewView(APIView):
    renderer_classes = [PDFRenderer]

    def get(self, request, organizer, event, position):
        op = get_object_or_404(
            OrderPosition,
            order__event__slug=event,
            order__event__organizer__slug=organizer,
            pk=position,
        )

        # Check if badges plugin is enabled
        if 'eventyay.plugins.badges' not in op.order.event.plugins:
            return Response(
                {'error': 'Badges plugin is not enabled for this event'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate the badge preview
        from django.core.exceptions import ValidationError as DjangoValidationError

        from .providers import BadgeOutputProvider
        from .utils import resolve_badge_layout_override

        try:
            layout_override = resolve_badge_layout_override(
                op.order.event, request.query_params.get('layout')
            )
        except DjangoValidationError as exc:
            return Response({'error': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        provider = BadgeOutputProvider(op.order.event)

        try:
            _, _, pdf_content = provider.generate(op, layout=layout_override)
            base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
            response = Response({'pdf_base64': base64_pdf}, status=status.HTTP_200_OK)
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BadgeDownloadView(APIView):
    renderer_classes = [JSONRenderer, PDFRenderer]

    def get(self, request, organizer, event, position):
        try:
            op = get_object_or_404(
                OrderPosition.objects.select_related(
                    'order',
                    'order__event',
                    'order__invoice_address',
                    'product',
                    'variation',
                    'addon_to',
                    'subevent',
                    'seat',
                ).prefetch_related('answers', 'answers__question', 'answers__options'),
                order__event__slug=event,
                order__event__organizer__slug=organizer,
                pk=position,
            )

            # Check if badges plugin is enabled
            if 'eventyay.plugins.badges' not in op.order.event.plugins:
                return Response(
                    {'error': 'Badges plugin is not enabled for this event'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Always regenerate so downloads never return a stale layout PDF.
            from django.core.exceptions import ValidationError as DjangoValidationError

            from .providers import BadgeOutputProvider
            from .utils import resolve_badge_layout_override

            try:
                layout_override = resolve_badge_layout_override(
                    op.order.event, request.query_params.get('layout')
                )
            except DjangoValidationError as exc:
                return Response({'error': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

            provider = BadgeOutputProvider(op.order.event)

            try:
                filename, mimetype, pdf_content = provider.generate(op, layout=layout_override)
                resp = HttpResponse(pdf_content, content_type=mimetype or 'application/pdf')
                resp['Content-Disposition'] = f'attachment; filename="{filename}"'
                return resp

            except Exception:
                # If immediate generation fails, fall back to async generation
                generate.apply_async(args=('orderposition', op.pk, 'badge'))
                return Response(
                    {
                        'status': 'generating',
                        'message': 'Badge generation has been started. Please retry in a few seconds.',
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
