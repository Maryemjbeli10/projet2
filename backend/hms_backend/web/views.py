from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import requests
from django.contrib.auth import get_user_model
import os
from django.conf import settings
from users.forms import OrdonnanceForm
from django.http import HttpResponse
from django.template.loader import render_to_string
import pdfkit
from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from users.models import Doctor, Patient, User, Appointment, Ordonnance
from users.serializers import PatientRegisterSerializer, AdminRegisterSerializer, DoctorRegisterSerializer

API_BASE = "http://127.0.0.1:8000/api/"

# ===============================
# 🏠 Page d'accueil publique
# ===============================
def homepage(request):
    role = request.session.get("role")
    if role == "admin":
        return redirect("admin_dashboard")
    elif role == "doctor":
        return redirect("doctor_dashboard")
    elif role == "patient":
        return redirect("patient_dashboard")
    return render(request, 'home.html')


# ===============================
# 👤 Inscription (Patient)
# ===============================
def register_page(request):
    if request.method == "POST":
        data = {
            "username": request.POST.get("username"),
            "email": request.POST.get("email"),
            "password": request.POST.get("password"),
            "full_name": request.POST.get("full_name"),
            "age": request.POST.get("age"),
            "phone": request.POST.get("phone"),
            "address": request.POST.get("address"),
        }

        serializer = PatientRegisterSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            messages.success(request, "Compte patient créé avec succès ✅")
            return redirect("login")
        else:
            messages.error(request, f"Erreur : {serializer.errors}")
    return render(request, "register.html")


# ===============================
# 🔐 Connexion
# ===============================
def login_page(request):
    if request.session.get("role") in ["admin", "doctor", "patient"]:
        return redirect(f"{request.session.get('role')}_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        try:
            response = requests.post(API_BASE + "users/login/", json={"username": username, "password": password})

            if response.status_code == 200:
                data = response.json()
                request.session["username"] = username
                request.session["access_token"] = data.get("access")
                request.session["refresh_token"] = data.get("refresh")
                request.session["role"] = data.get("role")

                messages.success(request, f"Bienvenue {username} 👋")

                return redirect(f"{data.get('role')}_dashboard")
            else:
                messages.error(request, "Nom d’utilisateur ou mot de passe invalide ❌")
        except requests.exceptions.ConnectionError:
            messages.error(request, "Erreur de connexion au serveur backend 🚫")

    return render(request, "login.html")


# ===============================
# 🚪 Déconnexion
# ===============================
def logout_user(request):
    request.session.flush()
    messages.success(request, "Déconnexion réussie 👋")
    return redirect("login")


# ===============================
# 🩺 Dashboard Médecin
# ===============================
def doctor_dashboard(request):
    role = request.session.get("role")
    username = request.session.get("username")
    access_token = request.session.get("access_token")

    if role != "doctor" or not access_token:
        messages.error(request, "Accès non autorisé.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    stats, schedule, alerts, weekly_performance_data = {}, [], [], []
    appointments_with_patients = []  # ✅ NOUVEAU

    try:
        resp_stats = requests.get(f"{API_BASE}doctors/{username}/stats/", headers=headers)
        stats = resp_stats.json() if resp_stats.status_code == 200 else {}

        resp_schedule = requests.get(f"{API_BASE}doctors/{username}/appointments/today/", headers=headers)
        schedule = resp_schedule.json() if resp_schedule.status_code == 200 else []

        resp_alerts = requests.get(f"{API_BASE}doctors/{username}/alerts/", headers=headers)
        alerts = resp_alerts.json() if resp_alerts.status_code == 200 else []

        resp_perf = requests.get(f"{API_BASE}doctors/{username}/weekly-performance/", headers=headers)
        weekly_performance_data = resp_perf.json() if resp_perf.status_code == 200 else []

        # ✅ NOUVEAU : récupérer tous les RDV avec patients
        resp_appointments = requests.get(f"{API_BASE}users/doctors/appointments/", headers=headers)
        appointments_with_patients = resp_appointments.json() if resp_appointments.status_code == 200 else []

    except requests.exceptions.RequestException:
        messages.warning(request, "Erreur de connexion au backend.")

    # 🩺 Récupérer le profil docteur
    try:
        doctor = Doctor.objects.get(user__username=username)
        doctor_name = doctor.full_name
        doctor_specialization = doctor.specialization
    except Doctor.DoesNotExist:
        doctor_name = username  # fallback
        doctor_specialization = "Non spécifiée"    

    # ----- Agenda : RDV confirmés -----
    confirmed_appointments = []
    try:
        resp_agenda = requests.get(f"{API_BASE}users/doctors/appointments/", headers=headers)
        if resp_agenda.status_code == 200:
            all_appointments = resp_agenda.json()
            confirmed_appointments = [
                a for a in all_appointments if a['status'] == 'CONFIRMED'
            ]
            confirmed_appointments.sort(key=lambda x: (x['date'], x['time']))
    except requests.exceptions.RequestException:
        pass

    return render(request, "dashboards/doctor_dashboard.html", {
        "username": username,
        "doctor_name": doctor_name,
        "doctor_specialization": doctor_specialization,
        "stats": stats,
        "schedule": schedule,
        "alerts": alerts,
        "weekly_performance_data": weekly_performance_data,
        "appointments_with_patients": appointments_with_patients,
        "confirmed_appointments": confirmed_appointments,
    })

# ===============================
# 🧑‍⚕️ Dashboard Patient
# ===============================
def patient_dashboard(request):
    role = request.session.get("role")
    username = request.session.get("username")
    access_token = request.session.get("access_token")
    print("Access token:", access_token)  # ← Ici, pour vérifier le token
    print("Username:", username) 

    if role != "patient" or not access_token:
        messages.error(request, "Accès refusé. Connectez-vous comme patient.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    doctors = []
    appointments = []
    ordonnances = []
    user_data = None
    patient_id = None

    try:
        # 🔍 Récupérer l’ID du patient connecté
        response_user = requests.get(API_BASE + f"users/profile/{username}/", headers=headers)
        if response_user.status_code == 200:
            user_data = response_user.json()
            patient_obj = Patient.objects.get(user__id=user_data.get("id"))
            patient_id = patient_obj.id  # <-- ID du Patient

            response_ords = requests.get(
                API_BASE + f"users/ordonnances/patient/{patient_id}/",
                headers=headers)

            if response_ords.status_code == 200:
                data = response_ords.json()
                if isinstance(data, dict) and "results" in data:
                    ordonnances = data["results"]
                else:
                    ordonnances = data
                print("Patient ID:", patient_id)
                print("Ordonnances récupérées:", ordonnances)
            else:
                messages.warning(request, "Impossible de charger vos ordonnances.")


            # 📅 Récupérer les rendez-vous du patient
            response_appointments = requests.get(API_BASE + f"users/appointments/patient/{patient_id}/", headers=headers)
            if response_appointments.status_code == 200:
                appointments = response_appointments.json()
            else:
                messages.warning(request, "Impossible de charger les rendez-vous.")

        # 👨‍⚕️ Liste des docteurs
            response_doctors = requests.get(f"{API_BASE}users/doctor-list/", headers=headers)
            if response_doctors.status_code == 200:
               doctors = response_doctors.json()

    except requests.exceptions.RequestException:
        messages.error(request, "Erreur de communication avec le serveur.")

    
    return render(request, "dashboards/patient_dashboard.html", {
        "username": username,
        "doctors": doctors,
        "appointments": appointments,
        "ordonnances": ordonnances, 
        "patient_id": patient_id,
        "access_token": access_token,
    })


# ===============================
# 🩺 Réserver un rendez-vous
# ===============================
def book_appointment_view(request, doctor_id):
    role = request.session.get("role")
    access_token = request.session.get("access_token")

    if role != "patient" or not access_token:
        messages.error(request, "Connectez-vous comme patient.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    doctor_details = {"id": doctor_id, "full_name": f"Docteur {doctor_id}", "specialization": "Médecin généraliste"}

    if request.method == "POST":
        appointment_data = {
            "doctor": doctor_id,
            "date": request.POST.get("date"),
            "time": request.POST.get("time"),
            "reason": request.POST.get("reason"),
        }

        try:
            response_booking = requests.post(API_BASE + "users/appointments/create/", json=appointment_data, headers=headers)
            if response_booking.status_code == 201:
                messages.success(request, "Rendez-vous réservé avec succès ✅")
                return redirect("patient_dashboard")
            else:
                messages.error(request, f"Erreur : {response_booking.json()}")
        except requests.exceptions.RequestException:
            messages.error(request, "Erreur réseau lors de la réservation.")

    return render(request, "book_appointment.html", {"doctor": doctor_details})



# ===============================
# 🧑‍💼 Dashboard Admin
# ===============================
def admin_dashboard(request):
    role = request.session.get("role")
    if role != "admin":
        return redirect("login")

    username = request.session.get("username")
    today = timezone.localdate()

    total_patients = User.objects.filter(role='patient').count()
    total_doctors = User.objects.filter(role='doctor').count()
    appointments_today = Appointment.objects.filter(date=today).count()

    recent_appointments = Appointment.objects.select_related('doctor', 'patient').order_by('-created_at')[:10]
    confirmed_appointments = Appointment.objects.filter(status='CONFIRMED').select_related('doctor', 'patient')
    context = {
        "username": username,
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "appointments_today": appointments_today,
        "recent_appointments": recent_appointments,
        "today": today,
        "confirmed_appointments": confirmed_appointments,
    }
    return render(request, "dashboards/admin_dashboard.html", context)


# ===============================
# 🧩 Gestion des utilisateurs (Admin)
# ===============================
def admin_add_user(request):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    if request.method == "POST":
        user_type = request.POST.get("user_type")
        data = {
            "username": request.POST.get("username"),
            "email": request.POST.get("email"),
            "password": request.POST.get("password"),
            "full_name": request.POST.get("full_name"),
            "age": request.POST.get("age"),
            "phone": request.POST.get("phone"),
            "address": request.POST.get("address"),
        }

        if user_type == "patient":
            serializer = PatientRegisterSerializer(data=data)
        elif user_type == "doctor":
            data["specialization"] = request.POST.get("specialization")
            data["experience_years"] = request.POST.get("experience_years")
            data["description"] = request.POST.get("description", "")
            serializer = DoctorRegisterSerializer(data=data)
        else:
            messages.error(request, "Type invalide.")
            return redirect("admin_add_user")

        if serializer.is_valid():
            serializer.save()
            messages.success(request, f"Compte {user_type} créé ✅")
            return redirect("admin_dashboard")
        else:
            messages.error(request, f"Erreur : {serializer.errors}")

    return render(request, "admin_add_user.html")


# ===============================
# 👥 Liste des patients et docteurs
# ===============================
def list_patients(request):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    patients = User.objects.filter(role="patient")
    return render(request, "admin_patients_list.html", {"patients": patients})


def list_doctors(request):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    doctors = User.objects.filter(role="doctor")
    return render(request, "admin_doctors_list.html", {"doctors": doctors})


# ===============================
# 👤 Profil utilisateur
# ===============================
def profile_info(request):
    username = request.session.get("username")
    role = request.session.get("role")
    access_token = request.session.get("access_token")

    if not access_token:
        messages.error(request, "Veuillez vous connecter.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(API_BASE + f"users/profile/{username}/", headers=headers)
        user_data = response.json() if response.status_code == 200 else {}
    except requests.exceptions.RequestException:
        user_data = {}

    return render(request, "profile_info.html", {"user_data": user_data})



from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404

@login_required
def delete_appointment_view(request, id):
    if request.method == "POST":
        appointment = get_object_or_404(Appointment, id=id)
        if request.user.role != "patient" or appointment.patient.user != request.user:
            raise PermissionDenied("Vous ne pouvez supprimer que vos propres rendez-vous.")
        appointment.delete()
        messages.success(request, "Rendez-vous supprimé avec succès ✅")
    return redirect("patient_dashboard")

def doctor_finished_patients_view(request):
    role = request.session.get("role")
    access_token = request.session.get("access_token")

    if role != "doctor" or not access_token:
        messages.error(request, "Accès refusé.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    patients = []

    try:
        response = requests.get(f"{API_BASE}users/doctor/finished-patients/", headers=headers)
        if response.status_code == 200:
            patients = response.json()
        else:
            messages.warning(request, "Erreur lors du chargement des patients.")
    except requests.exceptions.RequestException:
        messages.error(request, "Erreur de connexion au serveur.")

    return render(request, "doctor_finished_patients.html", {"patients": patients})

def doctor_weekly_schedule_view(request):
    role = request.session.get('role')
    access_token = request.session.get('access_token')

    if role != 'doctor' or not access_token:
        messages.error(request, 'Accès non autorisé.')
        return redirect('login')

    # On va appeler l’API en JS comme pour finished-patients
    return render(request, 'doctor_weekly_schedule.html', {
        'access_token': access_token
    })


def patient_history_view(request):
    role = request.session.get('role')
    access_token = request.session.get('access_token')

    if role != 'patient' or not access_token:
        messages.error(request, 'Accès non autorisé.')
        return redirect('login')

    return render(request, 'patient_history.html', {
        'access_token': access_token
    })


def create_ordonnance_view(request):

    # Vérifier si un docteur est connecté
    username = request.session.get("username")
    if not username:
        messages.error(request, "Veuillez vous connecter.")
        return redirect("doctor_login")

    # Récupérer l'utilisateur connecté
    user = User.objects.get(username=username)

    # Vérifier si c'est un docteur
    try:
        doctor = Doctor.objects.get(user=user)
    except Doctor.DoesNotExist:
        messages.error(request, "Vous devez être un docteur.")
        return redirect("doctor_dashboard")

    # Liste des patients
    patients = Patient.objects.all()

    if request.method == "POST":
        patient_id = request.POST.get("patient")
        diagnostic = request.POST.get("diagnostic")
        prescription = request.POST.get("prescription")
        notes = request.POST.get("notes")
        priority = request.POST.get("priority", "Normal")

        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Patient invalide.")
            return redirect("create_ordonnance")

        # Création de l'ordonnance
        ordonnance = Ordonnance.objects.create(
            doctor=doctor,
            patient=patient,
            prescription=prescription,
            diagnostic=diagnostic,
            notes=notes,
            priority=priority
        )

        messages.success(request, "Ordonnance créée avec succès.")
        return redirect("ordonnance_detail", ordonnance_id=ordonnance.id)

    # GET
    context = {
        "patients": patients,
    }
    return render(request, "create_ordonnance.html", context)

def ordonnance_detail_view(request, ordonnance_id):
    ordonnance = get_object_or_404(Ordonnance, id=ordonnance_id)

    # Vérifier que le docteur connecté est le propriétaire
    if request.session.get("role") != "doctor" or ordonnance.doctor.user.username != request.session.get("username"):
        messages.error(request, "Accès refusé.")
        return redirect("doctor_dashboard")

    return render(request, "ordonnance_detail.html", {"ordonnance": ordonnance})


def ordonnance_pdf_view(request, ordonnance_id):
    ordonnance = get_object_or_404(Ordonnance, id=ordonnance_id)

    # Sécurité : seul le docteur propriétaire peut télécharger
    if request.session.get("role") != "doctor" or ordonnance.doctor.user.username != request.session.get("username"):
        messages.error(request, "Accès refusé.")
        return redirect("doctor_dashboard")

    # Génération du PDF
    logo_abs_path = os.path.abspath(
        os.path.join(settings.BASE_DIR, "web", "static", "images", "logo.png")
    ).replace("\\", "/")
    logo_path = f"file:///{logo_abs_path}"

    html = render_to_string("ordonnance_pdf.html", {"ordonnance": ordonnance, "logo_path": logo_path})

    path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

    options = {
        'encoding': 'UTF-8',
        'enable-local-file-access': None,
    }

    pdf = pdfkit.from_string(html, False, configuration=config, options=options)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ordonnance_{ordonnance.id}.pdf"'
    return response




def patient_ordonnances_page(request):
    username = request.session.get("username")
    if not username:
        messages.error(request, "Veuillez vous connecter.")
        return redirect("login")

    try:
        user = User.objects.get(username=username)
        patient = Patient.objects.get(user=user)
    except (User.DoesNotExist, Patient.DoesNotExist):
        messages.error(request, "Profil patient introuvable.")
        return redirect("login")

    ordonnances = Ordonnance.objects.filter(patient=patient).order_by('-date_created')

    return render(request, 'patient_ordonnances.html', {'ordonnances': ordonnances})

def patient_ordonnance_pdf_view(request, ordonnance_id):
    print("🔍 ordonnance_id reçu :", ordonnance_id)
    ordonnance = get_object_or_404(Ordonnance, id=ordonnance_id)

    # 🔍 Prend le premier patient (test uniquement)
    patient = Patient.objects.first()
    if not patient:
        return HttpResponse("Aucun patient trouvé.")

    print("🔍 ordonnance.patient :", ordonnance.patient)
    print("🔍 patient utilisé :", patient)

    # Génération du PDF
    logo_abs_path = os.path.abspath(
        os.path.join(settings.BASE_DIR, "web", "static", "images", "logo.png")
    ).replace("\\", "/")
    logo_path = f"file:///{logo_abs_path}"

    html = render_to_string("ordonnance_pdf.html", {"ordonnance": ordonnance, "logo_path": logo_path})

    path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

    options = {
        'encoding': 'UTF-8',
        'enable-local-file-access': None,
    }

    pdf = pdfkit.from_string(html, False, configuration=config, options=options)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ordonnance_{ordonnance.id}.pdf"'
    return response

def generate_pdf(request, id):
    ordonnance = Ordonnance.objects.get(id=id)

    context = {
        "ordonnance": ordonnance,
        "logo_path": static('img/hms_logo.png'),
        "stamp_path": static('img/stamp.png')  # ← AJOUT
    }

    return render(request, "ordonnance_pdf.html", context)
def edit_doctor_inline(request, doctor_id):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    doctor = get_object_or_404(Doctor, id=doctor_id)
    user = doctor.user

    if request.method == "POST":
        # Mise à jour User
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.save()

        # Mise à jour Doctor
        doctor.full_name = request.POST.get("full_name")
        doctor.specialization = request.POST.get("specialization")
        doctor.phone = request.POST.get("phone")
        doctor.address = request.POST.get("address")
        doctor.experience_years = request.POST.get("experience_years")
        doctor.description = request.POST.get("description")
        doctor.save()

        messages.success(request, "Docteur modifié avec succès ✅")
        return redirect("list_doctors")

    return render(request, "admin_doctors_list.html", {"doctors": Doctor.objects.all()})

def delete_doctor_inline(request, doctor_id):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    doctor = get_object_or_404(Doctor, id=doctor_id)
    user = doctor.user
    user.delete()  # cascade → doctor supprimé
    messages.success(request, "Docteur supprimé avec succès ✅")
    return redirect("list_doctors")

def edit_patient_inline(request, patient_id):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    patient = get_object_or_404(Patient, id=patient_id)
    user = patient.user

    if request.method == "POST":
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.save()

        patient.full_name = request.POST.get("full_name")
        patient.age = request.POST.get("age")
        patient.phone = request.POST.get("phone")
        patient.address = request.POST.get("address")
        patient.save()

        messages.success(request, "Patient modifié avec succès ✅")
        return redirect("list_patients")

    return render(request, "admin_patients_list.html", {"patients": Patient.objects.all()})



def delete_patient_inline(request, patient_id):
    if request.session.get("role") != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("login")

    patient = get_object_or_404(Patient, id=patient_id)
    user = patient.user
    user.delete()  # cascade
    messages.success(request, "Patient supprimé avec succès ✅")
    return redirect("list_patients")


def doctor_ordonnances_view(request):
    role = request.session.get("role")
    access_token = request.session.get("access_token")

    if role != "doctor" or not access_token:
        messages.error(request, "Accès refusé.")
        return redirect("login")

    doctor = Doctor.objects.get(user__username=request.session["username"])

    # --- filtres ---
    search   = request.GET.get("search", "").strip()          # nom patient
    status_f = request.GET.get("status",  "")                # '' | 'Normal' | 'Urgent'

    qs = Ordonnance.objects.filter(doctor=doctor).select_related("patient").order_by("-date_created")

    if search:                       # filtre 1 : nom
        qs = qs.filter(patient__full_name__icontains=search)

    if status_f in ("Normal", "Urgent"):   # filtre 2 : priorité
        qs = qs.filter(priority=status_f)

    # liste déroulante : patients déjà présents dans les ordonnances du docteur
    patients = (Patient.objects
                       .filter(ordonnances__doctor=doctor)
                       .distinct()
                       .order_by("full_name"))

    return render(request, "doctor_ordonnances_list.html",
                  {"ordonnances": qs, "patients": patients})