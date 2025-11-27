from django.urls import path
from . import views, api_views

urlpatterns = [
    path('', views.homepage, name='home'),

    # Auth
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('logout/', views.logout_user, name='logout'),
    # Dashboards
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    #haroun_confugiration
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('api/admin/overview/', api_views.admin_overview, name='api_admin_overview'),
    path('add-user/admin/', views.admin_add_user, name='admin_add_user'),
    path("patients/admin/", views.list_patients, name="list_patients"),
    path("doctors/admin/", views.list_doctors, name="list_doctors"),
    path("profile/", views.profile_info, name="profile_info"),
    path('doctors/<int:doctor_id>/edit/', views.edit_doctor_inline, name='edit_doctor_inline'),
    path('doctors/<int:doctor_id>/delete/', views.delete_doctor_inline, name='delete_doctor_inline'),
    path('patients/<int:patient_id>/edit/', views.edit_patient_inline, name='edit_patient_inline'),
    path('patients/<int:patient_id>/delete/', views.delete_patient_inline, name='delete_patient_inline'),


    path('dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('book-appointment/<int:doctor_id>/', views.book_appointment_view, name='book_appointment'),
    path('appointments/<int:id>/delete/', views.delete_appointment_view, name='delete_appointment'),
    path('doctor/ordonnances/create/', views.create_ordonnance_view, name='create_ordonnance'),
    path('doctor/ordonnances/<int:ordonnance_id>/', views.ordonnance_detail_view, name='ordonnance_detail'),
    path('doctor/ordonnances/<int:ordonnance_id>/pdf/', views.ordonnance_pdf_view, name='ordonnance_pdf'),
    path('patient/ordonnances/', views.patient_ordonnances_page, name='patient_ordonnances'),
    path('patient/ordonnances/<int:ordonnance_id>/pdf/', views.patient_ordonnance_pdf_view, name='patient_ordonnance_pdf'),
    path('doctor/finished-patients/', views.doctor_finished_patients_view, name='doctor_finished_patients'),
    path('doctor/weekly-schedule/', views.doctor_weekly_schedule_view, name='doctor_weekly_schedule'),
    path('patient/history/', views.patient_history_view, name='patient_history'),
    path('doctor/ordonnances/', views.doctor_ordonnances_view, name='doctor_ordonnances'),

]