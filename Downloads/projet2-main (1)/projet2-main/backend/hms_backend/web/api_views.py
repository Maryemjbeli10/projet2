from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from users.models import User, Appointment

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_overview(request):
    today = timezone.localdate()
    data = {}
    try:
        data['total_patients'] = User.objects.filter(role='patient').count()
    except Exception:
        data['total_patients'] = 0
    try:
        data['total_doctors'] = User.objects.filter(role='doctor').count()
    except Exception:
        data['total_doctors'] = 0
    try:
        data['appointments_today'] = Appointment.objects.filter(date=today).count()
    except Exception:
        data['appointments_today'] = 0
    return Response(data)