from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from eventyay.base.services.loungemesh import token_exchange_payload, verify_loungemesh_token


@method_decorator(csrf_exempt, name='dispatch')
class LoungeMeshTokenAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw_token = (request.data.get('token') or '').strip()
        access = verify_loungemesh_token(raw_token)
        if not access:
            return Response({'error': 'invalid_token'}, status=403)
        payload = token_exchange_payload(access)
        if not payload:
            return Response({'error': 'forbidden'}, status=403)
        return Response(payload)


class LoungeMeshTokenRefreshView(LoungeMeshTokenAPIView):
    pass
