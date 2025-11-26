# backend/api/views_doctor_dashboard.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import date
from users.models import User, Appointment
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_stats(request, username):
    data = {
        "total_patients": 120,
        "today_appointments": 5,
        "new_reports": 2,
        "new_patients": 3,
        "doctor_name": "Dr. " + username.capitalize(),
        "doctor_specialization": "Cardiologie"
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_appointments_today(request, username):
    today = date.today().isoformat()
    data = [
        {"time": "09:00 AM", "name": "Patient 1", "status": "Confirmed"},
        {"time": "10:30 AM", "name": "Patient 2", "status": "Pending"},
    ]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_alerts(request, username):
    alerts = [
        {"type": "Drug Interaction", "patient": "Ali Ahmed", "value": "Interaction detected", "time": "09:45 AM", "drug": "Aspirin"},
    ]
    return Response(alerts)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_weekly_performance(request, username):
    data = [
        {"day": "Sat", "patients": 12},
        {"day": "Sun", "patients": 18},
        {"day": "Mon", "patients": 15},
        {"day": "Tue", "patients": 21},
        {"day": "Wed", "patients": 20},
        {"day": "Thu", "patients": 17},
        {"day": "Fri", "patients": 10},
    ]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_patients_list(request, username):
    """
    Retourne la liste des patients qui ont pris rendez-vous avec ce docteur
    """
    try:
        # Vérifier que le docteur existe
        doctor = User.objects.get(username=username, role='doctor')
        
        # Récupérer tous les patients qui ont des rendez-vous avec ce docteur
        patient_ids = Appointment.objects.filter(
            doctor=doctor
        ).values_list('patient_id', flat=True).distinct()
        
        # Récupérer les informations des patients
        patients = User.objects.filter(id__in=patient_ids, role='patient')
        
        # Serializer les données
        patients_data = []
        for patient in patients:
            patients_data.append({
                'username': patient.username,
                'full_name': patient.full_name,
                'email': patient.email,
                'age': patient.age,
                'phone': patient.phone,
                'address': patient.address,
            })
        
        return Response(patients_data, status=200)
        
    except User.DoesNotExist:
        return Response({"error": "Docteur introuvable"}, status=404)
    except Exception as e:
        return Response({"error": str(e)},status=500)