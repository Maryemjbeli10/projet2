from pyexpat.errors import messages
from django.shortcuts import redirect, render
import requests
from rest_framework import generics
from rest_framework import status
from web.views import API_BASE
from .models import User, Doctor, Patient , Appointment, Ordonnance
from .serializers import DoctorOrdonnanceSerializer, RegisterSerializer,PatientRegisterSerializer,AdminRegisterSerializer, DoctorRegisterSerializer, DoctorListSerializer, DoctorUpdateSerializer,PatientListSerializer, PatientUpdateSerializer,AppointmentSerializer, OrdonnanceSerializer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({"message": "Bienvenue " + request.user.username})
    
    
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        })
        
def home(request):
    return render(request, 'home.html')  # Assurez-vous que 'home.html' existe
    
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
class PatientRegisterView(generics.CreateAPIView):
    serializer_class = PatientRegisterSerializer
    permission_classes = [AllowAny]
class AdminRegisterView(generics.CreateAPIView):
    serializer_class = AdminRegisterSerializer
    permission_classes = [AllowAny]

class DoctorRegisterView(generics.CreateAPIView):
    serializer_class = DoctorRegisterSerializer
    permission_classes = [IsAdminUser]  # Seul l'admin peut créer

    queryset = User.objects.filter(role="doctor")

# class DoctorListView(generics.ListAPIView):
#     queryset = Doctor.objects.all() 
#     serializer_class = DoctorListSerializer
#     permission_classes = [IsAdminUser]
from rest_framework.permissions import IsAuthenticated # S'assurer que ceci est importé

class DoctorListView(APIView):
    # 💥 AJOUTER CECI : Seuls les utilisateurs connectés peuvent voir la liste 💥
    permission_classes = [IsAuthenticated] 
    
    def get(self, request):
        doctors = Doctor.objects.all()  # 🔹 Récupère tous les docteurs
        serializer = DoctorListSerializer(doctors, many=True)
        # 💥 ATTENTION : 'status' n'est pas directement importé, il faut utiliser drf.status 💥
        # Si vous utilisez status=status.HTTP_200_OK, assurez-vous de l'import :
        # from rest_framework import status 
        return Response(serializer.data, status=200) # Utiliser 200 si vous ne voulez pas importer drf.status

class DoctorUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Doctor.objects.all()
    serializer_class = DoctorUpdateSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'  # On utilise l'id du profil Doctor

class DoctorDeleteView(generics.DestroyAPIView):
    queryset = Doctor.objects.all()
    permission_classes = [IsAdminUser]
    lookup_field = 'id'  # On utilise l'id du profil Doctor

class PatientListView(generics.ListAPIView):
    queryset = Patient.objects.all()  # Tous les profils Patient
    serializer_class = PatientListSerializer
    permission_classes = [IsAdminUser]

class PatientUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientUpdateSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'  # On utilise l'id du profil Patient

class PatientDeleteView(generics.DestroyAPIView):
    queryset = Patient.objects.all()
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

class AppointmentCreateView(generics.CreateAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        if user.role != 'patient':
        # Lance une exception gérée par DRF pour un statut 403 Forbidden
           raise PermissionDenied("Seuls les patients peuvent réserver un rendez-vous.")

        try:
        # Assurez-vous que le profil Patient existe
           patient = user.patient_profile
        except Patient.DoesNotExist:
        # Ceci devrait en théorie ne pas arriver si le role est 'patient', 
        # mais c'est une sécurité.
           raise PermissionDenied("Votre compte Patient n'est pas correctement configuré.")

        serializer.save(patient=patient)

 
# ✅ Un docteur consulte ses rendez-vous
class DoctorAppointmentListView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'doctor':
            return Appointment.objects.filter(doctor=self.request.user.doctor_profile)
        elif self.request.user.role == 'admin':
            return Appointment.objects.all()
        else:
            return Appointment.objects.none()


# ✅ Le docteur peut confirmer, rejeter ou terminer le rendez-vous
class AppointmentStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        try:
            appointment = Appointment.objects.get(id=id)
        except Appointment.DoesNotExist:
            return Response({"error": "Rendez-vous introuvable."}, status=404)

        if request.user.role != 'doctor':
            return Response({"error": "Seul le docteur peut modifier le statut."}, status=403)

        status_value = request.data.get('status')
        if status_value not in ['CONFIRMED', 'CANCELLED', 'COMPLETED']:
            return Response({"error": "Statut invalide."}, status=400)

        appointment.status = status_value
        appointment.save()
        return Response({
            "message": f"Rendez-vous {status_value.lower()} avec succès.",
            "appointment": AppointmentSerializer(appointment).data
        })    
    
class PatientAppointmentListView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        try:
            patient = Patient.objects.get(user=user)
        except Patient.DoesNotExist:
            return Appointment.objects.none()  # Si patient introuvable → aucun résultat

        # 🛡️ Sécurité :
        # - Le patient ne peut voir que ses propres rendez-vous
        # - Un docteur ne peut pas voir les rendez-vous d’un autre patient
        # - L’admin peut tout voir
        if user.role == 'patient' and patient.user != user:
            return Appointment.objects.none()

        if user.role == 'doctor':
            # Un docteur ne voit que ses propres rendez-vous liés à ce patient
            return Appointment.objects.filter(doctor=user.doctor_profile, patient=patient)

        # L’admin voit tous les rendez-vous du patient
        return Appointment.objects.filter(patient=patient)

class MyDoctorAppointmentsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # 🛡️ Vérifie que c’est bien un docteur
        if user.role != 'doctor':
            return Appointment.objects.none()

        # 🩺 Récupère le profil docteur du user
        doctor = user.doctor_profile

        # 🔍 Retourne tous les rendez-vous liés à ce docteur
        return Appointment.objects.filter(doctor=doctor).order_by('-date', '-time')    





# ------------------------------
# 📝 Patient : modifier son RDV
# ------------------------------
class PatientAppointmentUpdateView(generics.UpdateAPIView):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_object(self):
        appointment = get_object_or_404(Appointment, id=self.kwargs['id'])
        user = self.request.user
        
        # Sécurité : seul le patient propriétaire peut modifier
        if user.role != 'patient' or appointment.patient.user != user:
            raise PermissionDenied("Vous ne pouvez modifier que vos propres rendez-vous.")
        
        # Ne pas permettre la modification si le RDV n'est plus en attente
        if appointment.status != 'PENDING':
            raise PermissionDenied("Ce rendez-vous ne peut plus être modifié.")
            
        return appointment

    def update(self, request, *args, **kwargs):
        partial = True
        instance = self.get_object()
        
        # Vérifier les conflits d'horaire
        doctor = request.data.get('doctor', instance.doctor.id)
        date = request.data.get('date', instance.date)
        time = request.data.get('time', instance.time)
        
        if Appointment.objects.filter(
            doctor_id=doctor, 
            date=date, 
            time=time
        ).exclude(id=instance.id).exists():
            return Response(
                {"error": "Ce créneau est déjà réservé pour ce docteur."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "message": "Rendez-vous modifié avec succès",
            "appointment": serializer.data
        })

# ------------------------------
# 🗑️  Patient : supprimer son RDV
# ------------------------------
class PatientAppointmentDeleteView(generics.DestroyAPIView):
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_object(self):
        appointment = get_object_or_404(Appointment, id=self.kwargs['id'])
        user = self.request.user
        if user.role != 'patient' or appointment.patient.user != user:
            raise PermissionDenied("Vous ne pouvez supprimer que vos propres rendez-vous.")
        return appointment    



class AppointmentDetailView(generics.RetrieveAPIView):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    lookup_field = 'id'



def edit_appointment_view(request, id):
    print("🔍 edit_appointment_view appelé avec id =", id)

    if request.session.get("role") != "patient":
        messages.error(request, "Accès interdit.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {request.session['access_token']}"}

    # 1️⃣ Récupérer les données actuelles du RDV
    url_detail = f"{API_BASE}appointments/{id}/"
    response = requests.get(url_detail, headers=headers)
    if response.status_code != 200:
        messages.error(request, "Rendez-vous introuvable.")
        return redirect("patient_dashboard")
    appointment = response.json()

    # 2️⃣ Soumission du formulaire
    if request.method == "POST":
        payload = {
            "doctor": appointment["doctor"],  # inchangé
            "date": request.POST["date"],
            "time": request.POST["time"],
            "reason": request.POST["reason"],
        }
        resp = requests.patch(
            f"{API_BASE}appointments/{id}/update/",
            json=payload,
            headers=headers,
        )
        if resp.status_code == 200:
            messages.success(request, "Rendez-vous modifié ✅")
            return redirect("patient_dashboard")
        else:
            messages.error(request, "Erreur lors de la modification.")

    # 3️⃣ Affichage du formulaire pré-rempli
    return render(request, "edit_appointment.html", {"appointment": appointment})  

from rest_framework.decorators import api_view, permission_classes

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_appointments_with_patients(request):
    user = request.user

    if user.role != 'doctor':
        return Response({"error": "Accès refusé. Seul un docteur peut consulter ses rendez-vous."}, status=403)

    appointments = Appointment.objects.filter(doctor=user.doctor_profile).select_related('patient').order_by('-date', '-time')

    data = [
        {
            "id": a.id,
            "date": a.date,
            "time": a.time,
            "reason": a.reason,
            "status": a.status,
            "patient": {
                "full_name": a.patient.full_name,
                "age": a.patient.age,
                "phone": a.patient.phone,
                "email": a.patient.user.email,
            }
        }
        for a in appointments
    ]

    return Response(data)

def admin_confirmed_appointments(request):
    if request.session.get("role") != "admin":
        return redirect("login")

    confirmed_appointments = Appointment.objects.filter(status='CONFIRMED').select_related('doctor', 'patient')

    return render(request, "admin_confirmed_appointments.html", {
        "confirmed_appointments": confirmed_appointments
    })

#liste complète des patients ayant un rendez-vous terminé
from django.db.models import Max

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_finished_patients(request):
    user = request.user
    if user.role != 'doctor':
        return Response({"error": "Accès refusé."}, status=403)

    doctor = user.doctor_profile
    search = request.GET.get('search', '').strip()

    # Patients avec au moins un RDV terminé
    qs = Patient.objects.filter(
        patient_appointments__doctor=doctor,
        patient_appointments__status='COMPLETED'
    ).annotate(
        last_visit=Max('patient_appointments__date')
    ).distinct()

    if search:
        qs = qs.filter(full_name__icontains=search)

    data = []
    for p in qs:
        last_appointment = Appointment.objects.filter(
            patient=p, doctor=doctor, status='COMPLETED'
        ).order_by('-date', '-time').first()

        data.append({
            "id": p.id,
            "full_name": p.full_name,
            "age": p.age,
            "phone": p.phone,
            "reason": last_appointment.reason,
            "last_visit": last_appointment.date,
        })

    return Response(data)

from datetime import timedelta
from django.utils import timezone
from django.utils import formats
from django.utils.dateformat import format
from django.utils.translation import gettext as _
from django.utils import translation

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_weekly_schedule(request):
    user = request.user
    if user.role != 'doctor':
        return Response({'error': 'Accès refusé.'}, status=403)

    doctor = user.doctor_profile
    today = timezone.now().date()

    # Forcer la langue française
    with translation.override('fr'):
        data = {}
        for i in range(6):
            day = today + timedelta(days=i)
            if day.weekday() == 6:  # dimanche
                continue

            rdv = Appointment.objects.filter(
                doctor=doctor,
                date=day,
                status='CONFIRMED'
            ).order_by('time').values('time', 'patient__full_name')

            # Jour en français
            jour_nom = format(day, 'l').capitalize()  # ex: Lundi
            label = f"{jour_nom} {day.strftime('%d/%m/%Y')}"

            data[jour_nom] = {
                'label': label,
                'rdvs': list(rdv)
            }

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_history(request):
    user = request.user
    if user.role != 'patient':
        return Response({"error": "Accès refusé."}, status=403)

    appointments = Appointment.objects.filter(
        patient=user.patient_profile,
        status='COMPLETED'
    ).order_by('-date', '-time').select_related('doctor')

    data = []
    for appt in appointments:
        data.append({
            "date": appt.date,
            "time": appt.time,
            "doctor_name": appt.doctor.full_name,
            "speciality": appt.doctor.specialization,
        })

    return Response(data)


from datetime import date

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_confirmed_appointments(request):
    """
    Prochains RDV CONFIRMED du patient connecté
    avec icônes & pastilles comme maquette
    """
    if request.user.role != 'patient':
        return Response({'error': 'Accès refusé.'}, status=403)

    patient = get_object_or_404(Patient, user=request.user)

    qs = (Appointment.objects
          .filter(patient=patient,
                  date__gte=date.today(),
                  status='CONFIRMED')
          .order_by('date', 'time')
          .select_related('doctor'))

    # regrouper par date
    grouped = {}
    for appt in qs:
        day = appt.date
        key = day.isoformat()
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            'id': appt.id,
            'date': appt.date,
            'time': appt.time,
            'reason': appt.reason,
            'doctor_name': appt.doctor.full_name,
            'speciality': appt.doctor.specialization,
            'icon': '①' if appt.time.hour < 12 else 'の' if appt.time.hour < 15 else 'O'
        })

    # tri chronologique
    sorted_keys = sorted(grouped.keys())
    sections = []
    today = date.today()
    for key in sorted_keys:
        day = date.fromisoformat(key)
        diff = (day - today).days
        if diff == 0:
            header = "Aujourd'hui"
        elif diff == 1:
            header = "Demain"
        elif diff == 2:
            header = "Dans 2 jours"
        elif diff <= 7:
            header = f"Dans {diff} jours"
        else:
            header = day.strftime('%A %d %B')

        items = grouped[key]
        sections.append({
            'header': header,
            'items': items
        })

    return Response(sections)
class PatientOrdonnanceListView(generics.ListAPIView):
    serializer_class = OrdonnanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Récupérer l'ID du patient depuis l'URL
        patient_id = self.kwargs.get('patient_id')
        patient = get_object_or_404(Patient, id=patient_id)

        # Debug : vérifier si le patient est correct
        print("Patient récupéré:", patient)

        # Récupérer les ordonnances du patient, triées par date décroissante
        ordonnances = Ordonnance.objects.filter(patient=patient).order_by('-date_created')

        # Debug : vérifier les ordonnances
        print("Ordonnances récupérées:", list(ordonnances.values('id', 'prescription', 'doctor_id', 'date_created')))

        return ordonnances
    

class DoctorOrdonnanceListView(generics.ListAPIView):
    serializer_class = DoctorOrdonnanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role != 'doctor':
            return Ordonnance.objects.none()

        qs = Ordonnance.objects.filter(
            doctor=user.doctor_profile
        ).select_related('patient').order_by('-date_created')

        search   = self.request.GET.get('search', '').strip()
        priority = self.request.GET.get('priority', '')

        # 1. filtre nom (ET seulement si on a tapé qqch)
        if search:
            qs = qs.filter(patient__full_name__icontains=search)

        # 2. filtre priorité (ET seulement si choisi)
        if priority in ('Normal', 'Urgent'):
            qs = qs.filter(priority=priority)

        return qs