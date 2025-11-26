from django import forms
from .models import Ordonnance, Patient
from users.models import Appointment, User

# users/forms.py
class OrdonnanceForm(forms.ModelForm):
    class Meta:
        model = Ordonnance
        fields = ['patient', 'prescription']

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)  # récupérer le docteur passé depuis la vue
        super().__init__(*args, **kwargs)
        if doctor:
            # Obtenir les patients liés aux rendez-vous du docteur
            patient_ids = Appointment.objects.filter(doctor=doctor).values_list('patient', flat=True)
            self.fields['patient'].queryset = Patient.objects.all() 